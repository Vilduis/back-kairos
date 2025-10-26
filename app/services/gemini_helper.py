# gemini_helper.py
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

from ..career import MAPA_CARRERAS, obtener_carreras_por_tipo

def generate_specific_career_recommendations(
    riasec_profile: Dict[str, float], 
    top3_categories: List[Dict[str, Any]], 
    free_text: str
) -> Dict[str, Any]:
    """
    Usa el perfil RIASEC y las categorías TOP 3 (calculadas localmente)
    para pedirle a Gemini que genere carreras específicas y explicaciones.
    Devuelve un JSON con la clave "top3_careers".
    Se limita estrictamente a las carreras definidas en career.py.
    """
    model = setup_client()

    # Construir mapa autorizado por categoría desde career.py
    allowed_map: Dict[str, List[str]] = {}
    ordered_categories: List[str] = []
    for item in top3_categories:
        cat = item.get("category")
        if not cat:
            continue
        ordered_categories.append(cat)
        allowed_map[cat] = MAPA_CARRERAS.get(cat, [])

    # Formatear la entrada para el prompt
    riasec_profile_str = ", ".join([f"{tipo}: {score:.2f}" for tipo, score in riasec_profile.items()])
    top3_categories_str = ", ".join([f"{item['category']} (Confianza: {item['score']:.0%})" for item in top3_categories])
    allowed_map_str = json.dumps(allowed_map, ensure_ascii=False)

    # Prompt con catálogo autorizado
    prompt = f"""
    Eres un orientador vocacional experto. Ya he analizado las respuestas de un estudiante
    y tengo su perfil RIASEC y las 3 categorías de carrera más afines según mi modelo.
    SOLO puedes recomendar carreras que estén en el catálogo autorizado.
    
    Contexto del Estudiante:
    - Perfil RIASEC (escala 0-1): {riasec_profile_str}
    - Categorías Top (de mi modelo): {top3_categories_str}
    - Intereses que escribió: "{free_text}"

    Catálogo autorizado (por categoría): {allowed_map_str}

    Tu Tarea:
    Basándote estrictamente en las 3 categorías que te di ({top3_categories_str}),
    genera EXACTAMENTE 3 carreras específicas para CADA categoría.
    Debes ELEGIR EXCLUSIVAMENTE nombres presentes en el catálogo autorizado por categoría.
    Para cada carrera, incluye una breve explicación de por qué encaja con su perfil.
    
    Devuelve SOLAMENTE un objeto JSON con una única clave: "top3_careers".
    El valor debe ser una lista de diccionarios, donde cada diccionario tiene:
    "career": (string) nombre exacto de la carrera del catálogo.
    "category": (string) categoría general a la que pertenece.
    "explanation": (string) breve explicación.
    """

    def _filter_and_fill(proposed: List[Dict[str, Any]]) -> Dict[str, Any]:
        # Filtrar a catálogo y rellenar hasta 3 por categoría
        by_cat: Dict[str, List[Dict[str, Any]]] = {cat: [] for cat in ordered_categories}
        for item in proposed or []:
            cat = item.get("category")
            name = item.get("career")
            if cat in allowed_map and name in allowed_map.get(cat, []):
                if len(by_cat[cat]) < 3:
                    by_cat[cat].append({
                        "career": name,
                        "category": cat,
                        "explanation": item.get("explanation") or "Seleccionada del catálogo local según tu perfil."
                    })
        # Rellenar con catálogo local si faltan
        for cat in ordered_categories:
            already = {x["career"] for x in by_cat[cat]}
            for name in allowed_map.get(cat, []):
                if len(by_cat[cat]) >= 3:
                    break
                if name in already:
                    continue
                by_cat[cat].append({
                    "career": name,
                    "category": cat,
                    "explanation": "Seleccionada del catálogo local según tu perfil RIASEC."
                })
        # Aplanar manteniendo orden de categorías
        flat: List[Dict[str, Any]] = []
        for cat in ordered_categories:
            flat.extend(by_cat.get(cat, [])[:3])
        return {"top3_careers": flat}

    if model:
        try:
            # Configurar para que la respuesta sea JSON
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
            result_text = (getattr(response, "text", "") or "").strip()
            if result_text:
                try:
                    result = json.loads(result_text)
                    proposed = result.get("top3_careers", [])
                    print("[Gemini] Carreras específicas generadas, aplicando restricción a catálogo")
                    return _filter_and_fill(proposed)
                except Exception as e:
                    print(f"Error al parsear JSON de Gemini: {e}")
        except Exception as e:
            print(f"[Gemini] Error en generación, fallback: {e}")

    # Fallback determinístico: elegir del catálogo autorizado
    fallback_list: List[Dict[str, Any]] = []
    for cat in ordered_categories:
        for name in allowed_map.get(cat, [])[:3]:
            fallback_list.append({
                "career": name,
                "category": cat,
                "explanation": "Seleccionada del catálogo autorizado por coincidencia de categoría."
            })
    print("[Gemini] Fallback activado con catálogo local")
    return {"top3_careers": fallback_list}

    # Prompt enfocado en la generación de carreras (no en el cálculo)
    prompt = f"""
    Eres un orientador vocacional experto. Ya he analizado las respuestas de un estudiante
    y tengo su perfil RIASEC y las 3 categorías de carrera más afines según mi modelo.
    
    Contexto del Estudiante:
    - Perfil RIASEC (escala 0-1): {riasec_profile_str}
    - Categorías Top (de mi modelo): {top3_categories_str}
    - Intereses que escribió: "{free_text}"

    Tu Tarea:
    Basándote *estrictamente* en las 3 categorías que te di ({top3_categories_str}),
    genera 3 carreras específicas para CADA categoría.
    Para cada carrera, incluye una breve explicación de por qué encaja con su perfil.
    
    Devuelve SOLAMENTE un objeto JSON con una única clave: "top3_careers".
    El valor debe ser una lista de diccionarios, donde cada diccionario tiene:
    "career": (string) El nombre de la carrera específica (ej. "Ingeniería de Software").
    "category": (string) La categoría general a la que pertenece (ej. "Tecnología").
    "explanation": (string) La breve explicación (ej. "Conecta tu alta 'I' con tu interés en crear...").

    Ejemplo de JSON que debes devolver:
    {{
        "top3_careers": [
            {{"career": "Geología", "category": "Ciencias Naturales", "explanation": "Ideal para tu lado Investigativo (I) y Realista (R)."}},
            {{"career": "Biotecnología", "category": "Ciencias Naturales", "explanation": "Combina tu alta 'I' con el trabajo de laboratorio."}},
            {{"career": "Desarrollo de Software", "category": "Tecnología", "explanation": "Perfecto para tu 'I' (lógica) y tu interés en 'programar'."}},
            {{"career": "Análisis de Datos", "category": "Tecnología", "explanation": "Usa tu lado 'I' y 'C' para encontrar patrones."}},
            {{"career": "Diseño UX/UI", "category": "Arte y Diseño", "explanation": "Combina 'A' (creatividad) con 'S' (ayudar a la gente)."}},
            {{"career": "Animación Digital", "category": "Arte y Diseño", "explanation": "Perfecto para tu lado Artístico (A) y técnico (I)."}}
        ]
    }}
    """

    if model:
        try:
            # Configurar para que la respuesta sea JSON
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
            # El modelo debería devolver JSON parseable
            result_text = getattr(response, "text", "") or ""
            result_text = result_text.strip()
            if result_text:
                result = json.loads(result_text)
                print("[Gemini] Carreras específicas generadas correctamente")
                return result
        except Exception as e:
            print(f"Error al parsear JSON de Gemini: {e}")
            # Caer en el fallback si falla

    print("[Gemini] Fallback activado: usando carreras de respaldo")
    return {
        "top3_careers": [
            {"career": "Diseñadora gráfica (Ejemplo)", "category": "Arte y Diseño", "explanation": "No se pudo conectar con el servicio de IA."},
            {"career": "Psicóloga clínica (Ejemplo)", "category": "Ciencias Sociales", "explanation": "Usando datos de respaldo."},
            {"career": "Docente de secundaria (Ejemplo)", "category": "Ciencias Sociales", "explanation": "Usando datos de respaldo."},
            {"career": "Ingeniero de Software (Ejemplo)", "category": "Tecnología", "explanation": "Usando datos de respaldo."},
        ]
    }

# --- NUEVO: Helper para modo abierto (3 interacciones) ---

def generate_open_followup(previous_texts: List[str]) -> str:
    """
    Genera una pregunta breve de seguimiento en español para el modo abierto.
    Usa Gemini si está disponible; si no, cae en plantillas determinísticas.
    """
    stage = len(previous_texts)
    last = previous_texts[-1] if previous_texts else ""

    model = setup_client() if _has_api_key() else None
    if model:
        try:
            prompt = (
                "Actúa como orientador vocacional.\n"
                f"El estudiante ha dicho: \"{last}\".\n"
                "Genera UNA sola pregunta breve, concreta y en español que profundice en sus intereses,\n"
                "sin repetir exactamente lo anterior. Mantén el tema relacionado con su mensaje.\n"
                "Responde solamente con la pregunta, sin texto adicional."
            )
            response = model.generate_content(prompt)
            text = (getattr(response, "text", "") or "").strip()
            if text:
                print("[Gemini] Pregunta de seguimiento generada por Gemini")
                return text
        except Exception as e:
            print(f"[Gemini] Error en followup, fallback: {e}")

    templates = [
        "¿Qué aspectos de programar te atraen más (resolver problemas, crear interfaces, datos, colaborar)?",
        "¿Qué tipo de proyectos te gustaría construir (apps móviles, backend, IA, videojuegos, análisis de datos)?",
        "¿En qué ambientes te sientes mejor (investigación, startups, corporaciones, educación, freelance)?"
    ]
    idx = min(stage, 2)
    base = templates[idx]
    if last:
        return f"Teniendo en cuenta que comentaste: \"{last}\", {base}"
    return base