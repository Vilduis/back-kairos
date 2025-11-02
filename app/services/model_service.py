# model_service.py (limpio)
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
import numpy as np
import joblib
import os
import json
from sklearn.metrics.pairwise import cosine_similarity

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

# --- Artefactos nuevos V6 ---
V6_MODEL_FILE = 'modelo_riasec_v6.pkl'
V6_VECTORIZER_FILE = 'vectorizer_riasec_v6.pkl'
CAREERS_JSON_FILE = 'careers_db_v6.json'

riasec_types = ['R', 'I', 'A', 'S', 'E', 'C']  # Importante mantener el orden

# Artefactos V6 (cargados bajo demanda)
v6_model = None
v6_vectorizer = None
CAREERS_DB: List[Dict[str, Any]] = []
CAREERS_VECTORS: Optional[np.ndarray] = None


def load_v6_models_if_needed():
    """Carga los artefactos del modelo V6 si aún no están en memoria."""
    global v6_model, v6_vectorizer
    if v6_model is None:
        model_path = get_artifact_path(V6_MODEL_FILE)
        print(f"Cargando modelo V6 desde: {model_path}")
        try:
            v6_model = joblib.load(model_path)
            print("✅ Modelo V6 cargado.")
        except FileNotFoundError:
            print(f"❌ ERROR: No se encontró el archivo del modelo V6: {model_path}")
        except Exception as e:
            print(f"❌ ERROR al cargar el modelo V6: {e}")
    if v6_vectorizer is None:
        vec_path = get_artifact_path(V6_VECTORIZER_FILE)
        print(f"Cargando vectorizador V6 desde: {vec_path}")
        try:
            v6_vectorizer = joblib.load(vec_path)
            print("✅ Vectorizador V6 cargado.")
        except FileNotFoundError:
            print(f"❌ ERROR: No se encontró el archivo del vectorizador V6: {vec_path}")
        except Exception as e:
            print(f"❌ ERROR al cargar el vectorizador V6: {e}")


def init_recommender_artifacts():
    """Carga los 3 paquetes al iniciar el servidor y prepara los vectores.
    - modelo_riasec_v6.pkl
    - vectorizer_riasec_v6.pkl
    - careers_db_v6.json -> CAREERS_DB y CAREERS_VECTORS (numpy.array)
    """
    global CAREERS_DB, CAREERS_VECTORS
    # Cargar modelo y vectorizador
    load_v6_models_if_needed()

    # Cargar JSON de carreras
    try:
        json_path = get_artifact_path(CAREERS_JSON_FILE)
        print(f"Cargando base de carreras desde: {json_path}")
        with open(json_path, "r", encoding="utf-8") as f:
            CAREERS_DB = json.load(f)
        # Procesar a numpy.array una sola vez
        CAREERS_VECTORS = np.array([
            np.array(item.get("riasec", [0, 0, 0, 0, 0, 0]), dtype=float)
            for item in CAREERS_DB
        ], dtype=float)
        print(f"✅ Base de carreras cargada: {len(CAREERS_DB)} carreras")
    except FileNotFoundError:
        print(f"❌ ERROR: No se encontró {CAREERS_JSON_FILE}")
        CAREERS_DB = []
        CAREERS_VECTORS = np.zeros((0, 6), dtype=float)
    except Exception as e:
        print(f"❌ ERROR al cargar {CAREERS_JSON_FILE}: {e}")
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
                synonyms = {
                    "R": "R", "REALISTA": "R", "REALISTIC": "R",
                    "I": "I", "INVESTIGATIVO": "I", "INVESTIGATIVE": "I", "INVESTIGADOR": "I",
                    "A": "A", "ARTISTICO": "A", "ARTÍSTICO": "A", "ARTISTIC": "A",
                    "S": "S", "SOCIAL": "S",
                    "E": "E", "EMPRENDEDOR": "E", "ENTERPRISING": "E",
                    "C": "C", "CONVENCIONAL": "C", "CONVENTIONAL": "C",
                }
                cat_key = synonyms.get(key_raw, key_raw if key_raw in riasec_types else None)
            except Exception:
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
                        except Exception:
                            pass
            if val is None and getattr(q, "question_type", None) == "scale" and ans.answer_text:
                t = str(ans.answer_text).strip().replace(",", ".")
                val = float(t)
        except Exception:
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
    def _normalize_text(s: str) -> str:
        return " ".join((s or "").strip().split())
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


def predict_profile_from_text_v6(text: str) -> dict[str, float]:
    """Usa el vectorizador y modelo V6 para predecir el perfil RIASEC (0-1)."""
    global v6_model, v6_vectorizer
    if not text:
        return {r: 0.0 for r in riasec_types}
    load_v6_models_if_needed()
    if v6_model is None or v6_vectorizer is None:
        return {r: 0.0 for r in riasec_types}
    try:
        X_input = v6_vectorizer.transform([text])
        pred = v6_model.predict(X_input)[0]
        pred = np.clip(pred, 0.0, 1.0)
        return {letter: float(pred[i]) for i, letter in enumerate(riasec_types)}
    except Exception as e:
        print(f"Error en predict_profile_from_text_v6: {e}")
        return {r: 0.0 for r in riasec_types}


# --- Base determinística de carreras (sin career.py) ---

def code_to_riasec_vector(code: str) -> List[float]:
    """Convierte un código tipo 'SEI' a vector ponderado RIASEC."""
    weights = {"R": 0.1, "I": 0.1, "A": 0.1, "S": 0.1, "E": 0.1, "C": 0.1}
    c = (code or "").upper().strip()
    if len(c) > 0 and c[0] in weights: weights[c[0]] = 1.0
    if len(c) > 1 and c[1] in weights: weights[c[1]] = 0.7
    if len(c) > 2 and c[2] in weights: weights[c[2]] = 0.4
    return [weights[letter] for letter in riasec_types]


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
        load_v6_models_if_needed()
        profile_0_to_1 = predict_profile_from_text_v6(answers_text)
    else:
        max_mcq_per_dim = 6 * 5
        profile_1_to_5 = {}
        for r_type in riasec_types:
            profile_1_to_5[r_type] = round(float(np.clip(mcq_scores.get(r_type, 0.0) / max_mcq_per_dim * 4.0 + 1.0, 1.0, 5.0)), 1)
        profile_0_to_1 = normalize_1_to_5_to_0_to_1(profile_1_to_5)

    free_text = (answers_text or "").strip()
    # Recomendaciones basadas en similitud (si la base está cargada); fallback: vacío
    top3: List[Dict[str, Any]] = _get_recommendations(profile_0_to_1, top_n=3)

    mode_numeric = 1.0 if (chat_mode or "guided") == "open" else 0.0
    metrics = {"model_version": 6.0, "source_mode": mode_numeric}

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

        def _describe(name: str, c_vec: np.ndarray) -> str:
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

        output: List[Dict[str, Any]] = []
        for i in idxs:
            item = CAREERS_DB[i]
            name = str(item.get("name", ""))
            c_vec = CAREERS_VECTORS[i]
            output.append({
                "career": name,
                "score": round(float(sims[i]), 2),
                "description": _describe(name, c_vec),
            })
        return output
    except Exception as e:
        print(f"Error en _get_recommendations: {e}")
        return []