# gemini_helper.py — Migrado a google-genai SDK (reemplaza google-generativeai deprecado)
import logging
import os
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

from ..utils.text import normalize_text as _normalize_text
from ..utils.heuristics import is_greeting as _is_greeting, is_task_request as _is_task_request, is_substantive_signal as _is_signal

try:
    from google import genai
except ImportError:
    logger.warning("google-genai SDK no disponible; Gemini desactivado")
    genai = None

# Importar settings para leer GEMINI_API_KEY desde .env
try:
    from ..config import settings
except ImportError:
    logger.warning("No se pudo importar settings; usando variables de entorno")
    settings = None  # fallback


# --- Utilidades internas ---

def _resolve_model_name(preferred: Optional[str] = None) -> str:
    """Devuelve el nombre del modelo a usar, sin llamadas a la API."""
    name = preferred or "gemini-1.5-flash"
    # El sufijo -latest no es válido en google-genai SDK v1+
    return name.replace("-latest", "")


# --- Singleton del cliente (se inicializa una sola vez) ---

_client = None
_model_name: Optional[str] = None
_client_initialized = False


def _get_api_key() -> Optional[str]:
    """Obtiene la API key desde settings o variable de entorno."""
    api_key = None
    try:
        api_key = getattr(settings, "GEMINI_API_KEY", None) if settings else None
    except Exception:
        api_key = None
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY")
    return api_key or None


def _has_api_key() -> bool:
    return bool(_get_api_key()) and genai is not None


def setup_client():
    """Devuelve el cliente singleton de google-genai. Se inicializa solo una vez."""
    global _client, _model_name, _client_initialized
    if _client_initialized:
        return _client, _model_name

    _client_initialized = True
    if not genai:
        logger.warning("[Gemini] SDK no disponible (google-genai no importado)")
        return None, None
    api_key = _get_api_key()
    if not api_key:
        logger.warning("[Gemini] GEMINI_API_KEY no configurada")
        return None, None
    try:
        preferred = (getattr(settings, "GEMINI_MODEL", None) if settings else None) or os.getenv("GEMINI_MODEL") or "gemini-1.5-flash"
        _client = genai.Client(api_key=api_key)
        _model_name = _resolve_model_name(preferred)
        logger.info("[Gemini] Cliente inicializado con modelo: %s", _model_name)
    except Exception as e:
        logger.error("[Gemini] Error inicializando cliente: %s", e)
        _client = None
        _model_name = None
    return _client, _model_name


# --- Cierre personalizado ---

def generate_closing_message(user_texts: List[str], student_name: Optional[str] = None) -> str:
    """
    Genera un mensaje de cierre personalizado que menciona temas específicos
    que el estudiante compartió antes de pedir confirmación de resultados.
    """
    non_empty = [t.strip() for t in user_texts if t.strip()]
    name_part = student_name.strip().split()[0] if student_name and student_name.strip() else ""

    if not non_empty:
        greeting = f"¡{name_part}, ya tengo" if name_part else "¡Ya tengo"
        return (
            f"{greeting} suficiente información para estimar tu perfil. "
            "¿Te muestro los resultados ahora? Responde 'sí' para verlos o 'no' para seguir."
        )

    client, model_name = setup_client() if _has_api_key() else (None, None)

    if client:
        try:
            conversation_summary = "\n".join(f"- {t}" for t in non_empty)
            name_instruction = f"El nombre del estudiante es {name_part}. Úsalo al inicio del mensaje.\n" if name_part else ""
            prompt = (
                "Eres Kairos, orientador vocacional cálido y cercano, en español latinoamericano.\n"
                f"{name_instruction}"
                "El estudiante de 5to de secundaria compartió lo siguiente en la conversación:\n"
                f"{conversation_summary}\n\n"
                "Escribe UN mensaje de cierre breve (máx. 35 palabras) que:\n"
                "1. Empiece con el nombre del estudiante si lo tienes.\n"
                "2. Mencione 2 o 3 temas concretos que compartió (ej: programación, IA, matemáticas).\n"
                "3. Diga que ya tienes suficiente información para estimar su perfil.\n"
                "4. Pregunte si quiere ver sus resultados.\n"
                "4. Use un tono cálido y motivador.\n"
                f"Ejemplo: '¡{name_part or 'Ana'}, con todo lo que me contaste sobre programación e IA ya tengo tu perfil! "
                "¿Quieres ver tus carreras recomendadas? Responde sí o no.'\n"
                "Responde SOLO con el mensaje, sin comillas."
            )
            response = client.models.generate_content(model=model_name, contents=prompt)
            text = (getattr(response, "text", "") or "").strip()
            if text:
                return text
        except Exception as e:
            logger.error("[Gemini] Error en closing message, usando fallback: %s", e)

    # Fallback: extraer palabras clave de los mensajes del usuario
    keywords = []
    kw_map = {
        "programar": "programación", "programación": "programación", "programacion": "programación",
        "inteligencia artificial": "IA", "machine learning": "machine learning", "ia ": "IA",
        "matemáticas": "matemáticas", "matematicas": "matemáticas",
        "ciencia": "ciencia", "tecnología": "tecnología", "tecnologia": "tecnología",
        "datos": "ciencia de datos", "diseñar": "diseño", "arte": "arte",
        "música": "música", "musica": "música", "deporte": "deporte",
        "investigar": "investigación", "analizar": "análisis",
    }
    full_text = " ".join(non_empty).lower()
    seen = set()
    for key, label in kw_map.items():
        if key in full_text and label not in seen:
            keywords.append(label)
            seen.add(label)
        if len(keywords) >= 3:
            break

    name_str = f"{name_part}, " if name_part else ""
    if keywords:
        topics = ", ".join(keywords[:-1]) + (" y " + keywords[-1] if len(keywords) > 1 else keywords[0])
        return (
            f"¡{name_str}con lo que me contaste sobre {topics} ya tengo suficiente "
            "para estimar tu perfil. ¿Te muestro tus carreras recomendadas? Responde 'sí' o 'no'."
        )

    return (
        f"¡{name_str}ya tengo suficiente información para estimar tu perfil vocacional. "
        "¿Te muestro los resultados ahora? Responde 'sí' para verlos o 'no' para seguir conversando."
    )


# --- Helper para modo abierto (3 interacciones) ---

def generate_open_followup(previous_texts: List[str], conversation_history: Optional[List[Dict[str, Any]]] = None, student_name: Optional[str] = None) -> str:
    """
    Genera una pregunta breve y amistosa para el modo abierto, orientada a recolectar
    señales útiles (gustos, habilidades, fortalezas, contexto preferido).
    Usa Gemini si está disponible; si no, usa plantillas contextuales.
    """
    last = (previous_texts[-1] if previous_texts else "").strip()

    signal_count = sum(1 for t in previous_texts if _is_signal(t))
    stage = signal_count  # usamos señales en lugar de simple conteo

    if _has_api_key():
        client, model_name = setup_client()
    else:
        client, model_name = None, None

    if client:
        try:
            name_part = student_name.strip().split()[0] if student_name and student_name.strip() else ""
            name_instruction = f"El nombre del estudiante es {name_part}. Úsalo naturalmente cuando sea apropiado.\n" if name_part else ""
            system_instruction = (
                "Eres Kairos, orientador vocacional cálido y cercano, en español latinoamericano, "
                "especializado en estudiantes de 17–19 años (5to de secundaria).\n"
                f"{name_instruction}"
                "Tu único objetivo es recolectar señales vocacionales útiles: gustos concretos, habilidades, fortalezas y contexto preferido de trabajo.\n\n"
                "REGLAS ESTRICTAS (siempre):\n"
                "- Responde con máximo 2 oraciones: primero un reconocimiento breve y concreto (5–8 palabras) de algo específico que dijo el estudiante, luego UNA sola pregunta.\n"
                "- El reconocimiento debe ser específico, NO genérico (prohibido: 'Qué interesante', 'Genial', 'Muy bien').\n"
                "- La pregunta debe tener máximo 15 palabras.\n"
                "- NUNCA repitas un tema que ya apareció en el historial.\n"
                "- NUNCA empieces con 'Y con lo que comentaste' ni 'Teniendo en cuenta que comentaste'.\n"
                "- Varía el inicio de cada respuesta; no empieces siempre de la misma forma.\n"
                "- Evita preguntas de doble opción largas.\n"
                "- Responde SOLO con el mensaje final. Sin comillas, sin explicaciones, sin meta-comentarios."
            )

            # Construir historial legible con delimitadores claros
            if conversation_history:
                history_lines = []
                for msg in conversation_history:
                    role = "Estudiante" if msg.get("role") == "user" else "Kairos"
                    history_lines.append(f"{role}: {msg.get('content', '').strip()}")
                history_str = "\n".join(history_lines)
            else:
                history_str = "\n".join(f"Estudiante: {t}" for t in previous_texts)

            if _is_greeting(last) or stage == 0:
                intent = (
                    "El último mensaje es un saludo o presentación inicial. "
                    "Responde con una pregunta amable para arrancar: pide gustos, habilidades o fortalezas con uno o dos ejemplos concretos."
                )
            elif stage <= 2:
                if _is_task_request(last):
                    intent = (
                        "El estudiante quiere analizar algo. Pide un ejemplo concreto de un reto o ejercicio "
                        "que le haya gustado y qué parte fue clave. Añade un micro-elogio suave."
                    )
                else:
                    intent = (
                        "El estudiante compartió 1–2 señales vocacionales. Formula una pregunta que profundice en lo que dijo: "
                        "qué parte disfruta más, qué lo motiva dentro de ese tema, o pide un ejemplo concreto."
                    )
            elif stage <= 4:
                intent = (
                    "Ya hay 3–4 señales sobre gustos y habilidades. Explora el contexto de trabajo preferido: "
                    "¿solo o en equipo?, ¿ambiente académico, empresa o startup?, ¿más creativo o más analítico? "
                    "Conéctalo con algo que el estudiante ya mencionó."
                )
            else:
                intent = (
                    "Hay muchas señales. Pide un matiz final sobre valores o condiciones de trabajo "
                    "(impacto social, estabilidad, innovación) basándote en lo que ya compartió."
                )

            contents = (
                f"### Historial de conversación:\n{history_str}\n\n"
                f"### Último mensaje del estudiante:\n\"{last}\"\n\n"
                f"### Tu tarea para este turno:\n{intent}"
            )
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config={"system_instruction": system_instruction},
            )
            text = (getattr(response, "text", "") or "").strip()
            if text:
                logger.info("[Gemini] Followup generado con IA (modelo: %s)", model_name)
                return text
        except Exception as e:
            logger.error("[Gemini] Error en followup, fallback: %s", e)

    # Fallback determinístico por etapas — rotación para evitar repetición
    if _is_greeting(last) or stage == 0:
        options = [
            "¿Qué actividades disfrutas y en qué te sientes fuerte?",
            "¿Qué materias o temas te llaman más la atención?",
            "¿Qué haces en tu tiempo libre que te salga de forma natural?",
        ]
    elif stage <= 2:
        if _is_task_request(last):
            options = [
                "¿Qué ejercicio o reto recuerdas que te gustó resolver?",
                "¿Qué tipo de problema te resulta más interesante atacar?",
            ]
        else:
            options = [
                "¿Qué parte disfrutas más: resolver problemas, analizar datos o crear cosas?",
                "¿Hay algún proyecto donde hayas dado lo mejor de ti?",
                "¿Qué se te da mejor: diseñar ideas, calcular o comunicarlas?",
                "¿Cuándo dices 'esto sí me gusta'? ¿Qué sueles estar haciendo?",
            ]
    elif stage <= 4:
        if _is_task_request(last):
            options = [
                "¿Qué tipo de problema disfrutas resolver: lógica, datos o diseño?",
                "¿Prefieres trabajar con números, personas o ideas?",
            ]
        else:
            options = [
                "¿Prefieres trabajar solo o en equipo?",
                "¿Te imaginas en una empresa grande, startup o investigando?",
                "¿Buscas algo más creativo o más analítico en tu trabajo ideal?",
            ]
    else:
        options = [
            "¿Qué te importa más: impacto social, estabilidad o innovar?",
            "¿Hay algo que no harías aunque pagara bien?",
            "¿Qué condición de trabajo sería innegociable para ti?",
        ]

    # Excluir preguntas que el bot ya hizo en esta conversación
    asked = {
        msg.get("content", "").strip()
        for msg in (conversation_history or [])
        if msg.get("role") == "bot"
    }
    available = [o for o in options if o not in asked] or options
    return available[abs(hash(last)) % len(available)]