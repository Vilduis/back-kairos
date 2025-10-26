# model_service.py
from typing import Dict, Any, List
from sqlalchemy.orm import Session
import numpy as np
import joblib
import os
import warnings
# Intentar usar pandas para pasar nombres de columnas a sklearn
try:
    import pandas as pd  # type: ignore
except ImportError:
    pd = None

# --- Imports de Modelos Locales ---
# (Asegúrate de tener scikit-learn instalado en tu backend: pip install scikit-learn)
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:
    print("Error: scikit-learn no está instalado. Instálalo con 'pip install scikit-learn'")
    TfidfVectorizer = None
    RandomForestClassifier = None
    cosine_similarity = None

# --- Imports de tus Modelos de DB ---
from ..models import (
    Evaluation as EvaluationModel,
    UserAnswer as UserAnswerModel,
    EvaluationResult as EvaluationResultModel,
    Question as QuestionModel,
    ChatMessage as ChatMessageModel,
    ChatSession as ChatSessionModel,
)
# --- Import del Nuevo Helper de Gemini ---
from .gemini_helper import generate_specific_career_recommendations
from ..config import settings

# --- Constantes y Carga de Modelos ---
BASE_MODEL_PATH = settings.MODEL_ARTIFACTS_PATH or os.path.join(os.path.dirname(__file__), 'artifacts')
MODEL_SAVE_FILE = 'random_forest_riasec_model.joblib'
VECTORIZER_SAVE_FILE = 'tfidf_vectorizer.joblib'
CENTROIDS_SAVE_FILE = 'tfidf_centroids.joblib'

riasec_types = ['R', 'I', 'A', 'S', 'E', 'C'] # Importante mantener el orden

# Variables globales para los modelos (se cargarán una vez)
rf_model = None
vectorizer = None
centroids = None

def load_models_if_needed():
    """Carga los 3 artefactos .joblib si aún no están en memoria."""
    global rf_model, vectorizer, centroids
    
    # Cargar Modelo Random Forest
    if rf_model is None:
        model_path = get_artifact_path(MODEL_SAVE_FILE)
        print(f"Cargando modelo RF desde: {model_path}")
        try:
            rf_model = joblib.load(model_path)
            print("✅ Modelo RF cargado.")
        except FileNotFoundError:
            print(f"❌ ERROR: No se encontró el archivo del modelo RF: {model_path}")
        except Exception as e:
            print(f"❌ ERROR al cargar el modelo RF: {e}")

    # Cargar Vectorizador TF-IDF
    if vectorizer is None:
        vectorizer_path = get_artifact_path(VECTORIZER_SAVE_FILE)
        print(f"Cargando vectorizador TF-IDF desde: {vectorizer_path}")
        try:
            vectorizer = joblib.load(vectorizer_path)
            print("✅ Vectorizador TF-IDF cargado.")
        except FileNotFoundError:
            print(f"❌ ERROR: No se encontró el archivo del vectorizador: {vectorizer_path}")
        except Exception as e:
            print(f"❌ ERROR al cargar el vectorizador: {e}")

    # Cargar Centroides NLP
    if centroids is None:
        centroids_path = get_artifact_path(CENTROIDS_SAVE_FILE)
        print(f"Cargando centroides NLP desde: {centroids_path}")
        try:
            centroids = joblib.load(centroids_path)
            print("✅ Centroides NLP cargados.")
        except FileNotFoundError:
            print(f"❌ ERROR: No se encontró el archivo de centroides: {centroids_path}")
        except Exception as e:
            print(f"❌ ERROR al cargar los centroides: {e}")

# --- Lógica de Agregación (Modificada) ---

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
    # --- MODIFICADO: Calcular SUMAS (como se entrenó el modelo) ---
    mcq_scores: Dict[str, float] = {k: 0.0 for k in riasec_types} 

    for ans, q in rows:
        cat_key = None
        if q.category and q.category.startswith("riasec_"):
            try:
                last = q.category.split("_")[-1]
                key_raw = (last or "").upper()
                # Normalizar el sufijo de la categoría a letra RIASEC
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
            # Si no hay selected_options, intenta parsear answer_text numérico para preguntas de tipo escala
            if val is None and getattr(q, "question_type", None) == "scale" and ans.answer_text:
                t = str(ans.answer_text).strip().replace(",", ".")
                val = float(t)
        except Exception:
            val = None
        if val is not None and cat_key and cat_key in mcq_scores:
            # SUMAR en lugar de promediar, como en entrenamiento
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

# --- Lógica de Procesamiento NLP (Nueva) ---

def get_nlp_scores(text: str) -> dict[str, float]:
    """Calcula los puntajes de similitud RIASEC usando los modelos cargados."""
    global vectorizer, centroids
    
    if not text or not vectorizer or not centroids:
        return {r_type: 0.0 for r_type in riasec_types}

    try:
        text_vector = vectorizer.transform([text])
        nlp_scores = {}
        for r_type in riasec_types:
            centroid_vector = centroids[r_type].reshape(1, -1)
            similarity = cosine_similarity(text_vector, centroid_vector)[0][0]
            nlp_scores[r_type] = float(similarity)
        return nlp_scores
    except Exception as e:
        print(f"Error en get_nlp_scores: {e}")
        return {r_type: 0.0 for r_type in riasec_types}

# --- Lógica de Perfil Final (Nueva) ---

def calculate_final_profile(mcq_scores: dict[str, float], nlp_scores: dict[str, float], weight_mcq: float = 0.70, weight_nlp: float = 0.30) -> tuple[dict[str, float], np.ndarray]:
    """Combina y escala los puntajes para el perfil final."""
    
    # Constantes de escalado (como en el entrenamiento)
    max_mcq_per_dim = 6 * 5 # Max teórico MCQ (6 preguntas * 5 puntos)
    max_nlp_per_dim = 1.0   # Max teórico Similitud Coseno
    
    profile_0_to_1: dict[str, float] = {}
    for r_type in riasec_types:
        scaled_mcq = mcq_scores.get(r_type, 0) / max_mcq_per_dim if max_mcq_per_dim > 0 else 0
        scaled_nlp = nlp_scores.get(r_type, 0) / max_nlp_per_dim if max_nlp_per_dim > 0 else 0
        profile_0_to_1[r_type] = (weight_mcq * scaled_mcq) + (weight_nlp * scaled_nlp)

    # Re-escalar el perfil 0-1 a la escala de entrenamiento del RF (~0-30)
    profile_for_model = np.array(
        [profile_0_to_1[r_type] * max_mcq_per_dim for r_type in riasec_types]
    ).reshape(1, -1)

    return profile_0_to_1, profile_for_model

# --- Función Principal (Modificada) ---

def generate_and_save_results(db: Session, evaluation_id: int) -> EvaluationResultModel:
    """
    Función principal actualizada:
    1. Carga los modelos .joblib
    2. Agrega puntajes MCQ y texto libre de la DB
    3. Calcula puntajes NLP localmente
    4. Combina y escala para crear el perfil final
    5. Ejecuta el Random Forest local para obtener Top 3 CATEGORÍAS
    6. Llama a Gemini para obtener carreras ESPECÍFICAS
    7. Guarda el resultado final en la DB
    """
    
    # Paso 1: Cargar modelos locales
    load_models_if_needed()
    
    # Verificar que los modelos estén cargados
    if not rf_model or not vectorizer or not centroids:
        print("ERROR: Los modelos locales no están cargados. Abortando.")
        # Crear un resultado consistente con el esquema para evitar errores de validación
        result_error = EvaluationResultModel(
            evaluation_id=evaluation_id,
            riasec_scores={k: 0.0 for k in riasec_types},
            top_careers=[],
            metrics={"model_accuracy_static": 0.0, "error_models_not_loaded": 1.0}
        )
        db.add(result_error)
        db.commit()
        db.refresh(result_error)
        return result_error

    # Paso 2: Agregar datos de la DB
    agg = aggregate_answers_for_evaluation(db, evaluation_id)
    mcq_scores = agg["mcq_scores"]
    answers_text = agg["answers_text"]

    # Determinar ponderaciones según modo de chat
    evaluation_rec = db.query(EvaluationModel).filter(EvaluationModel.evaluation_id == evaluation_id).first()
    chat_mode = None
    if evaluation_rec:
        chat_session = db.query(ChatSessionModel).filter(ChatSessionModel.session_id == evaluation_rec.session_id).first()
        if chat_session:
            chat_mode = chat_session.chat_mode
        if not chat_mode:
            chat_mode = getattr(evaluation_rec, "evaluation_mode", None)
    if chat_mode == "open":
        weight_mcq, weight_nlp = 0.0, 1.0
    else:
        weight_mcq, weight_nlp = 0.70, 0.30

    # Paso 3: Calcular puntajes NLP
    nlp_scores = get_nlp_scores(answers_text)

    # Paso 4: Combinar y escalar (con ponderación por modo)
    profile_0_to_1, profile_for_model = calculate_final_profile(mcq_scores, nlp_scores, weight_mcq, weight_nlp)

    # Paso 5: Ejecutar Random Forest local
    # Construir entrada con nombres de características si es posible para evitar el warning
    X = profile_for_model
    if hasattr(rf_model, "feature_names_in_"):
        feature_names = list(getattr(rf_model, "feature_names_in_"))
        # Mapear nombres de columnas del modelo a letras RIASEC
        feature_synonyms = {
            # Inglés
            "Realistic": "R", "Investigative": "I", "Artistic": "A", "Social": "S", "Enterprising": "E", "Conventional": "C",
            # Minúsculas inglés
            "realistic": "R", "investigative": "I", "artistic": "A", "social": "S", "enterprising": "E", "conventional": "C",
            # Español
            "Realista": "R", "Investigativo": "I", "Artístico": "A", "Social": "S", "Emprendedor": "E", "Convencional": "C",
            # Minúsculas español
            "realista": "R", "investigativo": "I", "artístico": "A", "artistico": "A", "social": "S", "emprendedor": "E", "convencional": "C",
            # Prefijos de entrenamiento (Colab)
            "Score_R": "R", "Score_I": "I", "Score_A": "A", "Score_S": "S", "Score_E": "E", "Score_C": "C",
            "score_R": "R", "score_I": "I", "score_A": "A", "score_S": "S", "score_E": "E", "score_C": "C",
            # Letras directas
            "R": "R", "I": "I", "A": "A", "S": "S", "E": "E", "C": "C",
        }
        # Valores por tipo (en la escala del modelo)
        values_by_type = {t: float(profile_for_model[0][i]) for i, t in enumerate(riasec_types)}
        if pd is not None:
            row = {}
            for col in feature_names:
                letter = feature_synonyms.get(col, col if col in riasec_types else None)
                val = values_by_type.get(letter, 0.0)
                row[col] = val
            X = pd.DataFrame([row], columns=feature_names)
            # Debug
            print(f"[RF DEBUG] feature_names: {feature_names}")
            print(f"[RF DEBUG] assembled_row: {row}")
        else:
            idx_map = {t: i for i, t in enumerate(riasec_types)}
            ordered = []
            for col in feature_names:
                letter = feature_synonyms.get(col, col if col in riasec_types else None)
                idx = idx_map.get(letter, idx_map.get("R", 0))
                ordered.append(float(profile_for_model[0][idx]))
            X = np.array(ordered).reshape(1, -1)
            # Suprimir el warning específico de nombres si no tenemos pandas
            warnings.filterwarnings(
                "ignore",
                message=(
                    "X does not have valid feature names, but RandomForestClassifier was fitted with feature names"
                ),
                category=UserWarning,
            )
            # Debug
            print(f"[RF DEBUG] feature_names: {feature_names}")
            print(f"[RF DEBUG] assembled_ordered: {ordered}")
    # Si el modelo no expone feature_names_in_, usar el orden R,I,A,S,E,C directamente
    else:
        X = profile_for_model

    probabilities = rf_model.predict_proba(X)
    classes = rf_model.classes_
    prob_list = list(zip(classes, probabilities[0]))
    prob_list.sort(key=lambda x: x[1], reverse=True)
    # Debug
    try:
        print(f"[RF DEBUG] classes: {list(classes)}")
        print(f"[RF DEBUG] probabilities: {[round(float(x),4) for x in probabilities[0]]}")
    except Exception:
        pass

    top3_categories_list = []
    for career_category, score in prob_list[:3]:
        top3_categories_list.append({"category": career_category, "score": round(float(score), 4)})
    # Debug
    print(f"[RF DEBUG] top3: {top3_categories_list}")

    # Paso 6: Llamar a Gemini para obtener carreras específicas
    # (El helper ahora solo genera las carreras, no el perfil)
    gemini_results = generate_specific_career_recommendations(
        riasec_profile=profile_0_to_1,
        top3_categories=top3_categories_list,
        free_text=answers_text
    )

    # Paso 7: Guardar el resultado final
    result = EvaluationResultModel(
        evaluation_id=evaluation_id,
        riasec_scores={k: round(v, 4) for k, v in profile_0_to_1.items()}, # Perfil calculado localmente
        top_careers=gemini_results.get("top3_careers", []), # Carreras específicas del catálogo/LLM
        metrics={"model_accuracy_static": 0.925} # Métrica estática del modelo
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    
    return result

# --- Funciones no modificadas (si las necesitas) ---
def ensure_evaluation_for_session(db: Session, user_id: int, session_id: int) -> EvaluationModel:
    evaluation = db.query(EvaluationModel).filter(EvaluationModel.session_id == session_id).first()
    if evaluation:
        return evaluation
    # Ajustar el modo de la evaluación según la sesión
    chat_session = db.query(ChatSessionModel).filter(ChatSessionModel.session_id == session_id).first()
    eval_mode = chat_session.chat_mode if chat_session else "guided"
    evaluation = EvaluationModel(user_id=user_id, session_id=session_id, evaluation_mode=eval_mode)
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return evaluation


def get_artifact_path(filename: str) -> str:
    base = settings.MODEL_ARTIFACTS_PATH or os.path.join(os.path.dirname(__file__), 'artifacts')
    path = os.path.abspath(os.path.join(base, filename))
    return path