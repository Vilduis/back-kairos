# gemini_helper.py (limpio)
import os
import json
from typing import Dict, Any, List, Optional

try:
    import google.generativeai as genai
except Exception:
    genai = None

# Importar settings para leer GEMINI_API_KEY desde .env
try:
    from ..config import settings
except Exception:
    settings = None  # fallback

# --- Utilidades internas ---

def _clean_model_name(name: str) -> str:
    return name.split("/")[-1] if name.startswith("models/") else name


def _resolve_supported_model(preferred: Optional[str] = None) -> str:
    """Devuelve un modelo que soporte generateContent.
    Intenta respetar el `preferred` si existe en la lista o en alguna variante.
    """
    if not genai:
        # Valor por defecto estable si la librería no está disponible
        return preferred or "gemini-1.5-flash"
    try:
        available = list(genai.list_models())
        supported = []
        for m in available:
            methods = getattr(m, "supported_generation_methods", []) or getattr(m, "generation_methods", []) or []
            if "generateContent" in methods:
                supported.append(_clean_model_name(m.name))

        # Si tenemos preferencia, intentamos encontrar coincidencia exacta o por base
        if preferred:
            p = preferred
            if p in supported:
                return p
            base_p = p.replace("-latest", "").replace("-001", "")
            for s in supported:
                base_s = s.replace("-latest", "").replace("-001", "")
                if base_s == base_p:
                    return s

        # Heurística de selección por orden de preferencia
        preference_order = [
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "gemini-pro",
            "gemini-1.0-pro",
            "gemini-1.5-flash-001",
            "gemini-1.5-pro-001",
        ]
        for pref in preference_order:
            for s in supported:
                if s.startswith(pref):
                    return s

        # Último recurso: primer modelo soportado o caída al valor estable
        return supported[0] if supported else (preferred or "gemini-1.5-flash")
    except Exception as e:
        print(f"[Gemini] No se pudieron listar modelos, usando preferido: {preferred or 'gemini-1.5-flash'} ({e})")
        return preferred or "gemini-1.5-flash"

# --- Función de Configuración ---

def _has_api_key() -> bool:
    api_key = None
    # Priorizar settings si está disponible
    try:
        api_key = getattr(settings, "GEMINI_API_KEY", None) if settings else None
    except Exception:
        api_key = None
    # Fallback a variable de entorno directa
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY")
    return bool(api_key) and genai is not None


def setup_client():
    if not genai:
        return None
    # Obtener API key desde settings o entorno
    api_key = getattr(settings, "GEMINI_API_KEY", None) if settings else None
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        genai.configure(api_key=api_key)
        preferred = (getattr(settings, "GEMINI_MODEL", None) if settings else None) or os.getenv("GEMINI_MODEL")
        model_name = _resolve_supported_model(preferred)  # seleccionar modelo soportado
        print(f"[Gemini] Configurado modelo: {model_name}")
        return genai.GenerativeModel(model_name)
    except Exception as e:
        print(f"[Gemini] Error configurando cliente: {e}")
        return None

# --- Función Principal ---
# Ya no dependemos de un catálogo local de carreras; el modelo las provee.

def generate_model_careers(
    riasec_profile: Dict[str, float],
    free_text: str,
    n: int = 3,
) -> List[Dict[str, Any]]:
    """
    Obtiene del modelo n carreras con un puntaje de afinidad.
    Devuelve List[{career: str, score: float}] en rango [0.0, 1.0].
    """
    model = setup_client()
    riasec_profile_str = ", ".join([f"{k}: {float(v):.2f}" for k, v in riasec_profile.items()])
    prompt = f"""
    Eres un orientador vocacional. Con el perfil RIASEC (0-1) y el texto libre
    del estudiante, recomienda exactamente {n} carreras específicas.

    Perfil RIASEC: {riasec_profile_str}
    Intereses: "{free_text}"

    Devuelve SOLO JSON con esta forma exacta:
    {{"items":[{{"career":"...","score":0.95}}]}}

    Reglas:
    - "career" debe ser un nombre de carrera concreto (string).
    - "score" debe ser un número entre 0.0 y 1.0 (float) que refleje afinidad.
    - No incluyas otros campos como categoría ni explicación.
    - No agregues texto fuera del JSON.
    """

    def _empty() -> List[Dict[str, Any]]:
        # Importante: No devolver carreras inventadas.
        # Si el modelo no responde o hay error, devolvemos lista vacía.
        return []

    if not model:
        return _empty()

    try:
        try:
            GenerationConfig = getattr(genai, "types", None)
            generation_config = GenerationConfig.GenerationConfig(
                response_mime_type="application/json"
            ) if GenerationConfig else genai.GenerationConfig(
                response_mime_type="application/json"
            )
        except Exception:
            generation_config = None

        response = model.generate_content(prompt, generation_config=generation_config) if generation_config else model.generate_content(prompt)
        text = (getattr(response, "text", "") or "").strip()
        if not text:
            return _empty()
        try:
            data = json.loads(text)
            raw_items = data.get("items", [])
            if not isinstance(raw_items, list):
                return _empty()

            # Normalizar estructura y aplicar fallback de score si falta
            normalized: List[Dict[str, Any]] = []
            base_score = 0.95
            step = 0.02
            for idx, it in enumerate(raw_items[:n]):
                name = str(it.get("career", "")).strip()
                score = it.get("score", None)
                try:
                    score = float(score)
                except Exception:
                    score = None
                if score is None:
                    score = max(0.5, base_score - idx * step)
                # Clip al rango [0,1]
                score = 0.0 if score < 0 else (1.0 if score > 1.0 else score)
                if name:
                    normalized.append({"career": name, "score": float(score)})
            return normalized
        except Exception as e:
            print(f"[Gemini] Error parseando JSON de carreras: {e}")
            return _empty()
    except Exception as e:
        print(f"[Gemini] Error generando carreras del modelo: {e}")
        return _empty()

# --- Helper para modo abierto (3 interacciones) ---

def generate_open_followup(previous_texts: List[str]) -> str:
    """
    Genera una pregunta breve y amistosa para el modo abierto, orientada a recolectar
    señales útiles (gustos, habilidades, fortalezas, contexto preferido).
    Usa Gemini si está disponible; si no, usa plantillas contextuales.
    """
    last = (previous_texts[-1] if previous_texts else "").strip()

    def _normalize(t: str) -> str:
        t = (t or "").strip().lower()
        return t.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")

    def _is_greeting(t: str) -> bool:
        tt = _normalize(t)
        if not tt:
            return False
        greetings = [
            "hola", "holi", "buenas", "buen dia", "buenos dias", "buenas tardes", "buenas noches",
            "hey", "que tal", "saludos"
        ]
        return any(tt == g or tt.startswith(g) for g in greetings) or len(tt) <= 5

    def _is_task_request(t: str) -> bool:
        tt = _normalize(t)
        if not tt:
            return False
        cues = [
            "puedes", "podrias", "ayudame", "ayuda", "analizar", "analizar la situacion",
            "resolver ejercicio", "responder ejercicio", "explicar", "explicame", "como resolver"
        ]
        return any(c in tt for c in cues)

    def _is_signal(t: str) -> bool:
        tt = _normalize(t)
        if _is_greeting(tt):
            return False
        signal_keywords = [
            "me gusta", "me encanta", "prefiero", "disfruto", "me interesa", "me atrae", "soy bueno", "se me da",
            "habilidad", "fortaleza", "fan", "aficion", "pasiones", "crear", "diseñar", "dibujar", "pintar",
            "programar", "investigar", "analizar", "enseñar", "comunicar", "organizar", "liderar", "colaborar",
            "arte", "musica", "deporte", "tecnologia", "ciencia", "matematicas", "negocios", "marketing",
            "cultura", "paisajes", "historias", "escribir"
        ]
        long_enough = len(tt) >= 15
        return any(kw in tt for kw in signal_keywords) or long_enough

    signal_count = sum(1 for t in previous_texts if _is_signal(t))
    stage = signal_count  # usamos señales en lugar de simple conteo

    model = setup_client() if _has_api_key() else None
    if model:
        try:
            persona = (
                "Actúa como un orientador vocacional cálido y cercano (Kairos), en español latinoamericano,\n"
                "orientado a estudiantes de 17–19 años (5to de secundaria).\n"
                "Objetivo: recolectar 5–6 señales útiles (gustos concretos, habilidades, fortalezas, contexto preferido).\n"
                "Reglas:\n"
                "- Escribe una sola pregunta breve (máx. 18 palabras).\n"
                "- No repitas textualmente lo dicho; profundiza o abre ángulos nuevos.\n"
                "- Sé amable, motivador y específico según el último mensaje.\n"
                "- Evita frases genéricas; propone ejemplos si el estudiante está vago.\n"
                "- En las primeras 3 interacciones, no uses frases como 'para afinar', 'cuéntame un poquito más';\n"
                "  usa un tono fluido y cercano con micro-elogios breves.\n"
            )
            if _is_greeting(last) or stage == 0:
                intent = (
                    "Si el último mensaje es un saludo o no da señales, responde con una pregunta amable para iniciar: "
                    "pide gustos, habilidades o fortalezas con uno o dos ejemplos."
                )
            elif stage <= 2:
                if _is_task_request(last):
                    intent = (
                        "El estudiante pidió analizar/resolver un ejercicio. Responde con una sola pregunta breve, "
                        "cálida y cercana, pidiendo un ejemplo concreto: 'Claro, cuéntame un ejercicio o reto que te gustó "
                        "resolver y qué paso fue clave para ti'. Evita repetir preguntas previas y añade un micro-elogio suave."
                    )
                else:
                    intent = (
                        "El estudiante compartió 1–2 señales. Formula una pregunta fluida y cercana, con un micro-elogio, "
                        "para entender qué parte disfruta más (resolver problemas, analizar datos, crear cosas) sin sonar rígido."
                    )
            elif stage <= 4:
                intent = (
                    "Ya hay 3–4 señales. Explora contexto preferido: trabajo en equipo vs. individual, más creativo vs. "
                    "analítico, ambientes (educación, empresa, startup, independiente)."
                )
            else:
                intent = (
                    "Hay 5+ señales. Solicita un matiz final (p. ej., valores importantes o condiciones de trabajo) "
                    "para cerrar bien el perfil."
                )
            prompt = (
                persona
                + intent
                + "\nÚltimo mensaje del estudiante: \"" + last + "\"\n"
                + "Responde SOLO con la pregunta breve."
            )
            response = model.generate_content(prompt)
            text = (getattr(response, "text", "") or "").strip()
            if text:
                print("[Gemini] Pregunta de seguimiento generada por Gemini")
                return text
        except Exception as e:
            print(f"[Gemini] Error en followup, fallback: {e}")

    # Fallback determinístico por etapas (señales)
    if _is_greeting(last) or stage == 0:
        base = "¡Qué gusto saludarte! ¿Qué actividades disfrutas y en qué te sientes fuerte?"
    elif stage <= 2:
        base = (
            "Cuéntame un ejemplo concreto: ¿qué ejercicio o problema te gustó resolver y qué paso fue clave?"
            if _is_task_request(last)
            else "¿Qué parte disfrutas más: resolver problemas, analizar datos o crear cosas?"
        )
    elif stage <= 4:
        base = (
            "¿Qué tipo de problema disfrutas resolver (lógica, datos, diseño)? Cuéntame uno breve."
            if _is_task_request(last)
            else "¿Prefieres crear y explorar ideas o analizar y resolver problemas? ¿Solo o en equipo?"
        )
    else:
        base = "¿Qué valores o condiciones de trabajo son importantes para ti (p. ej., impacto, estabilidad, creatividad)?"

    if last:
        if stage <= 2:
            return f"Y con lo que comentaste, {base}"
        return f"Teniendo en cuenta que comentaste: \"{last}\", {base}"
    return base