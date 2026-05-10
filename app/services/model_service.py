import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
import numpy as np
import joblib
import os
import json
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

from ..utils.text import normalize_text as _normalize_text

# --- Imports de tus Modelos de DB ---
from ..models import (
    Evaluation as EvaluationModel,
    UserAnswer as UserAnswerModel,
    EvaluationResult as EvaluationResultModel,
    Question as QuestionModel,
    ChatMessage as ChatMessageModel,
    ChatSession as ChatSessionModel,
)

from ..config import settings

# --- Artefactos V8 ---
V8_PIPELINE_FILE = 'pipeline_riasec_v8_20260427.pkl'
CAREERS_JSON_FILE = 'careers_db_v8_20260427.json'

riasec_types = ['R', 'I', 'A', 'S', 'E', 'C']  # Importante mantener el orden

# Mapeo canónico de variantes de categoría RIASEC → letra única
_RIASEC_SYNONYMS: dict[str, str] = {
    "R": "R", "REALISTA": "R", "REALISTIC": "R",
    "I": "I", "INVESTIGATIVO": "I", "INVESTIGATIVE": "I", "INVESTIGADOR": "I",
    "A": "A", "ARTISTICO": "A", "ARTÍSTICO": "A", "ARTISTIC": "A",
    "S": "S", "SOCIAL": "S",
    "E": "E", "EMPRENDEDOR": "E", "ENTERPRISING": "E",
    "C": "C", "CONVENCIONAL": "C", "CONVENTIONAL": "C",
}

# Pipeline V8 (cargado bajo demanda)
v8_pipeline = None
CAREERS_DB: List[Dict[str, Any]] = []
CAREERS_VECTORS: Optional[np.ndarray] = None


def load_v8_pipeline_if_needed():
    """Carga el pipeline V8 si aún no está en memoria."""
    global v8_pipeline
    if v8_pipeline is None:
        path = get_artifact_path(V8_PIPELINE_FILE)
        logger.info("Cargando pipeline V8 desde: %s", path)
        try:
            v8_pipeline = joblib.load(path)
            logger.info("Pipeline V8 cargado.")
        except FileNotFoundError:
            logger.error("No se encontró el pipeline V8: %s", path)
        except Exception as e:
            logger.error("Error al cargar el pipeline V8: %s", e)


def init_recommender_artifacts():
    """Carga los artefactos V8 al iniciar el servidor y prepara los vectores.
    - pipeline_riasec_v8_20260427.pkl -> v8_pipeline
    - careers_db_v8_20260427.json -> CAREERS_DB y CAREERS_VECTORS (numpy.array)
    """
    global CAREERS_DB, CAREERS_VECTORS
    load_v8_pipeline_if_needed()

    # Cargar JSON de carreras
    try:
        json_path = get_artifact_path(CAREERS_JSON_FILE)
        logger.info("Cargando base de carreras desde: %s", json_path)
        with open(json_path, "r", encoding="utf-8") as f:
            CAREERS_DB = json.load(f)
        # Procesar a numpy.array una sola vez
        CAREERS_VECTORS = np.array([
            np.array(item.get("riasec", [0, 0, 0, 0, 0, 0]), dtype=float)
            for item in CAREERS_DB
        ], dtype=float)
        logger.info("Base de carreras cargada: %d carreras", len(CAREERS_DB))
    except FileNotFoundError:
        logger.error("No se encontró %s", CAREERS_JSON_FILE)
        CAREERS_DB = []
        CAREERS_VECTORS = np.zeros((0, 6), dtype=float)
    except Exception as e:
        logger.error("Error al cargar %s: %s", CAREERS_JSON_FILE, e)
        CAREERS_DB = []
        CAREERS_VECTORS = np.zeros((0, 6), dtype=float)


# --- Lógica de Agregación (simplificada) ---

def aggregate_answers_for_evaluation(db: Session, evaluation_id: int) -> Dict[str, Any]:
    """
    Agrega las respuestas del usuario.
    Calcula la SUMA de los puntajes MCQ (P1-P36).
    Recopila todo el texto libre.
    """
    evaluation = db.query(EvaluationModel).filter(EvaluationModel.evaluation_id == evaluation_id).first()
    if not evaluation:
        return {"answers_text": "", "mcq_scores": {k: 0 for k in riasec_types}}

    rows = (
        db.query(UserAnswerModel, QuestionModel)
        .join(QuestionModel, UserAnswerModel.question_id == QuestionModel.question_id)
        .filter(UserAnswerModel.evaluation_id == evaluation_id)
        .all()
    )

    text_parts: List[str] = []
    mcq_scores: Dict[str, float] = {k: 0.0 for k in riasec_types}

    for ans, q in rows:
        cat_key = None
        if q.category and q.category.startswith("riasec_"):
            try:
                last = q.category.split("_")[-1]
                key_raw = (last or "").upper()
                cat_key = _RIASEC_SYNONYMS.get(key_raw, key_raw if key_raw in riasec_types else None)
            except Exception as e:
                logger.warning("Error resolviendo categoría RIASEC para pregunta %s: %s", q.question_id, e)
                cat_key = None

        # Agregar texto libre de preguntas abiertas
        if ans.answer_text:
            text_parts.append(ans.answer_text.strip())

        # Procesar puntajes de escala (Likert P1-P36, modo guiado)
        val = None
        try:
            data = ans.selected_options if isinstance(ans.selected_options, dict) else None
            if data:
                if "scale" in data:
                    val = float(data["scale"])
                elif "value" in data:
                    val = float(data["value"])
                elif "selected" in data:
                    sel = data.get("selected")
                    if isinstance(sel, list) and len(sel) > 0:
                        try:
                            val = float(sel[0])
                        except Exception as e:
                            logger.warning("Error convirtiendo selected_options[0] a float: %s", e)
            if val is None and getattr(q, "question_type", None) == "scale" and ans.answer_text:
                t = str(ans.answer_text).strip().replace(",", ".")
                val = float(t)
        except Exception as e:
            logger.warning("Error parseando valor de respuesta para evaluación %s: %s", evaluation_id, e)
            val = None
        if val is not None and cat_key and cat_key in mcq_scores:
            mcq_scores[cat_key] += val

    # Agregar mensajes abiertos del chat
    chat_msgs = (
        db.query(ChatMessageModel)
        .filter(ChatMessageModel.session_id == evaluation.session_id, ChatMessageModel.message_type == "user")
        .order_by(ChatMessageModel.sent_at.asc())
        .all()
    )
    for m in chat_msgs:
        text_parts.append(m.content)

    # Deduplicar y normalizar texto antes de unir
    seen = set()
    normalized_parts: List[str] = []
    for t in filter(None, text_parts):
        nt = _normalize_text(t)
        if nt and nt not in seen:
            normalized_parts.append(nt)
            seen.add(nt)

    answers_text = "\n".join(normalized_parts)
    return {"answers_text": answers_text, "mcq_scores": mcq_scores}


# --- Utilidades de conversión de perfiles (V6) ---

def normalize_1_to_5_to_0_to_1(profile_1_to_5: dict[str, float]) -> dict[str, float]:
    """Convierte un perfil en escala 1-5 a 0-1 (lineal)."""
    norm: dict[str, float] = {}
    for k in riasec_types:
        v = float(profile_1_to_5.get(k, 1.0))
        norm[k] = float(np.clip((v - 1.0) / 4.0, 0.0, 1.0))
    return norm


def convert_0_to_1_to_1_to_5(profile_0_to_1: dict[str, float]) -> dict[str, float]:
    """Convierte un perfil 0-1 a 1-5 para visualización (redondeo a 0.1)."""
    scaled: dict[str, float] = {}
    for k in riasec_types:
        v = float(profile_0_to_1.get(k, 0.0))
        scaled[k] = round(float(np.clip(v * 4.0 + 1.0, 1.0, 5.0)), 1)
    return scaled


def predict_profile_from_text_v8(text: str) -> dict[str, float]:
    """Usa el pipeline V8 para predecir el perfil RIASEC (0-1)."""
    global v8_pipeline
    if not text:
        return {r: 0.0 for r in riasec_types}
    load_v8_pipeline_if_needed()
    if v8_pipeline is None:
        return {r: 0.0 for r in riasec_types}
    try:
        pred = v8_pipeline.predict([text])[0]
        pred = np.clip(pred, 0.0, 1.0)
        return {letter: float(pred[i]) for i, letter in enumerate(riasec_types)}
    except Exception as e:
        logger.error("Error en predict_profile_from_text_v8: %s", e)
        return {r: 0.0 for r in riasec_types}


# --- Función Principal ---

def generate_and_save_results(db: Session, evaluation_id: int) -> EvaluationResultModel:
    """
    Flujo principal:
    1) Carga datos de la evaluación (MCQ y texto libre)
    2) Determina modo (guided vs open)
    3) Construye perfil RIASEC:
       - guided: normaliza 1–5 -> 0–1 (sin modelo de texto)
       - open: usa V6 texto->perfil (carga artefactos sólo en este modo)
    4) Obtiene Top 3 del modelo externo
    5) Persistir el resultado en la DB
    """

    # Paso 1: Agregar datos de la DB
    agg = aggregate_answers_for_evaluation(db, evaluation_id)
    mcq_scores = agg["mcq_scores"]
    answers_text = agg["answers_text"]

    # Determinar modo (guiado vs abierto)
    evaluation_rec = db.query(EvaluationModel).filter(EvaluationModel.evaluation_id == evaluation_id).first()
    chat_mode = None
    if evaluation_rec:
        chat_session = db.query(ChatSessionModel).filter(ChatSessionModel.session_id == evaluation_rec.session_id).first()
        if chat_session:
            chat_mode = chat_session.chat_mode
        if not chat_mode:
            chat_mode = getattr(evaluation_rec, "evaluation_mode", None)

    # Paso 2: Construir perfil según modo
    if (chat_mode or "guided") == "open":
        load_v8_pipeline_if_needed()
        profile_0_to_1 = predict_profile_from_text_v8(answers_text)
    else:
        # 6 preguntas por dimensión, escala Likert 1–5
        # min posible = 6*1 = 6, max posible = 6*5 = 30
        # Fórmula: (suma - min) / (max - min) * 4 + 1  →  rango exacto [1.0, 5.0]
        min_mcq_per_dim = 6 * 1   # 6
        max_mcq_per_dim = 6 * 5   # 30
        profile_1_to_5 = {}
        for r_type in riasec_types:
            score = mcq_scores.get(r_type, 0.0)
            profile_1_to_5[r_type] = round(float(np.clip(
                (score - min_mcq_per_dim) / (max_mcq_per_dim - min_mcq_per_dim) * 4.0 + 1.0,
                1.0, 5.0
            )), 1)
        profile_0_to_1 = normalize_1_to_5_to_0_to_1(profile_1_to_5)

    # Recomendaciones basadas en similitud (si la base está cargada); fallback: vacío
    top3: List[Dict[str, Any]] = _get_recommendations(profile_0_to_1, top_n=3)

    mode_numeric = 1.0 if (chat_mode or "guided") == "open" else 0.0
    metrics = {"model_version": 8.0, "source_mode": mode_numeric}

    existing = (
        db.query(EvaluationResultModel)
        .filter(EvaluationResultModel.evaluation_id == evaluation_id)
        .first()
    )
    if existing:
        existing.riasec_scores = {k: round(float(v), 4) for k, v in profile_0_to_1.items()}
        existing.top_careers = top3
        existing.metrics = metrics
        db.commit()
        db.refresh(existing)
        return existing
    else:
        result = EvaluationResultModel(
            evaluation_id=evaluation_id,
            riasec_scores={k: round(float(v), 4) for k, v in profile_0_to_1.items()},
            top_careers=top3,
            metrics=metrics,
        )
        db.add(result)
        db.commit()
        db.refresh(result)
    return result


# --- Funciones auxiliares ---

def ensure_evaluation_for_session(db: Session, user_id: int, session_id: int) -> EvaluationModel:
    evaluation = db.query(EvaluationModel).filter(EvaluationModel.session_id == session_id).first()
    if evaluation:
        return evaluation
    chat_session = db.query(ChatSessionModel).filter(ChatSessionModel.session_id == session_id).first()
    eval_mode = chat_session.chat_mode if chat_session else "guided"
    evaluation = EvaluationModel(user_id=user_id, session_id=session_id, evaluation_mode=eval_mode)
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return evaluation


def get_artifact_path(filename: str) -> str:
    """Busca el archivo en:
    1) Mismo directorio que este módulo
    2) settings.MODEL_ARTIFACTS_PATH
    3) subcarpeta 'artifacts' dentro del directorio de este módulo
    """
    module_dir = os.path.dirname(__file__)
    candidates = [
        os.path.abspath(os.path.join(module_dir, filename)),
    ]
    if getattr(settings, "MODEL_ARTIFACTS_PATH", None):
        candidates.append(os.path.abspath(os.path.join(settings.MODEL_ARTIFACTS_PATH, filename)))
    candidates.append(os.path.abspath(os.path.join(module_dir, 'artifacts', filename)))

    for p in candidates:
        if os.path.exists(p):
            return p
    # Si no existe ninguno, devolvemos la última ruta como predeterminada
    return candidates[-1]


def _describe_career(name: str, c_vec: np.ndarray, user_top: list) -> str:
    """Genera una descripción personalizada de una carrera basada en el perfil RIASEC del usuario."""
    labels = {
        "R": "Realista",
        "I": "Investigador",
        "A": "Artístico",
        "S": "Social",
        "E": "Emprendedor",
        "C": "Convencional",
    }
    traits = {
        "R": "proyectos prácticos y resultados tangibles",
        "I": "análisis y resolución de problemas complejos",
        "A": "creación y diseño de soluciones creativas",
        "S": "comunicación y trabajo colaborativo",
        "E": "liderazgo, negociación y dirección de iniciativas",
        "C": "organización, planificación y seguimiento de procesos",
    }
    order = np.argsort(c_vec)[::-1]
    ct = [riasec_types[int(i)] for i in order[:2]]
    p1 = f"Se alinea con tus intereses {labels[user_top[0]]} ({user_top[0]})"
    p1 += f" y {labels[user_top[1]]} ({user_top[1]})."
    p2 = f" En {name}, el enfoque {labels[ct[0]]} ({ct[0]}) favorece {traits[ct[0]]}."
    p3 = f" También aporta {traits[ct[1]]} desde {labels[ct[1]]} ({ct[1]})."
    return (p1 + p2 + p3).strip()


def _get_recommendations(profile_0_to_1: Dict[str, float], top_n: int = 3) -> List[Dict[str, Any]]:
    """Compara el perfil del usuario (0-1) contra CAREERS_VECTORS y devuelve top N.
    Salida: [{"career": name, "score": float, "description": str}]
    """
    global CAREERS_DB, CAREERS_VECTORS
    try:
        if CAREERS_VECTORS is None or CAREERS_VECTORS.shape[0] == 0:
            return []
        user_vec = np.array([profile_0_to_1.get(k, 0.0) for k in riasec_types], dtype=float).reshape(1, -1)
        sims = cosine_similarity(user_vec, CAREERS_VECTORS)[0]
        idxs = np.argsort(sims)[::-1][:top_n]
        user_order = np.argsort(user_vec.flatten())[::-1]
        user_top = [riasec_types[int(i)] for i in user_order[:2]]

        output: List[Dict[str, Any]] = []
        for i in idxs:
            item = CAREERS_DB[i]
            name = str(item.get("name", ""))
            c_vec = CAREERS_VECTORS[i]
            output.append({
                "career": name,
                "score": round(float(sims[i]), 2),
                "description": _describe_career(name, c_vec, user_top),
                "faculty": str(item.get("faculty", "")),
            })
        return output
    except Exception as e:
        logger.error("Error en _get_recommendations: %s", e)
        return []