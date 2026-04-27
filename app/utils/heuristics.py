from .text import normalize_text as _normalize


def is_greeting(text: str) -> bool:
    t = _normalize(text)
    if not t:
        return False
    greetings = [
        "hola", "holi", "buenas", "buen dia", "buenos dias", "buenas tardes", "buenas noches",
        "hey", "que tal", "saludos",
    ]
    return any(t == g or t.startswith(g) for g in greetings) or len(t) <= 5


def is_acceptance(text: str) -> bool:
    t = _normalize(text)
    words = set(t.split())
    short_yes = {"si", "yes", "ok", "okay", "dale", "claro"}
    if words & short_yes:
        return True
    verbs = {"ver", "mostrar", "muestrame", "dame", "dar", "entregar",
             "obtener", "tener", "quiero", "necesito", "podrias", "puedes"}
    nouns = {"resultado", "resultados"}
    if (words & verbs) and (words & nouns):
        return True
    extra = [
        "verlos", "ver resultados", "mostrar resultados", "quiero ver", "quiero mis resultados",
        "mi resultado", "dame mi resultado", "darme el resultado", "darme mi resultado",
    ]
    return any(p in t for p in extra)


def is_negative(text: str) -> bool:
    t = _normalize(text)
    negatives = ["no", "no aun", "todavia no", "prefiero seguir", "seguir conversando"]
    return any(t == n or n in t for n in negatives)


def is_task_request(text: str) -> bool:
    t = _normalize(text)
    if not t:
        return False
    cues = [
        "puedes", "podrias", "ayudame", "ayuda", "analizar", "analizar la situacion",
        "resolver ejercicio", "responder ejercicio", "explicar", "explicame", "como resolver",
    ]
    return any(c in t for c in cues)


_SIGNAL_KEYWORDS = [
    "me gusta", "me encanta", "prefiero", "disfruto", "me interesa", "me atrae", "soy bueno", "se me da",
    "me vacila", "me motiva", "me apasiona", "me llama",
    "habilidad", "fortaleza", "fan", "aficion", "pasiones", "crear", "diseñar", "dibujar", "pintar",
    "programar", "investigar", "analizar", "analizar datos", "enseñar", "comunicar", "organizar", "liderar", "colaborar",
    "arte", "musica", "deporte", "tecnologia", "ciencia", "matematicas", "numeros", "negocios", "marketing",
    "cultura", "paisajes", "historias", "escribir", "acertijos", "rompecabezas", "ayudar",
]


def is_substantive_signal(text: str) -> bool:
    if not text:
        return False
    t = _normalize(text)
    if is_greeting(t) or is_acceptance(t) or is_negative(t):
        return False
    long_enough = len(t) >= 15
    has_keyword = any(kw in t for kw in _SIGNAL_KEYWORDS)
    return has_keyword or long_enough


_ANCHOR_KEYWORDS = [
    "me gusta", "me encanta", "prefiero", "disfruto", "me interesa", "me atrae",
    "soy bueno", "se me da", "me vacila", "me motiva", "me apasiona", "me llama",
]

_COUNT_KEYWORDS = [
    "habilidad", "fortaleza", "crear", "diseñar", "dibujar", "pintar",
    "programar", "investigar", "analizar", "analizar datos", "enseñar", "comunicar",
    "organizar", "liderar", "colaborar", "arte", "musica", "deporte", "tecnologia",
    "ciencia", "matematicas", "numeros", "negocios", "marketing", "cultura", "escribir",
    "acertijos", "rompecabezas", "ayudar",
]


def count_signals(text: str) -> int:
    """Cuenta señales vocacionales en un mensaje. Máximo 4 por mensaje."""
    if not text:
        return 0
    t = _normalize(text)
    if is_greeting(t) or is_acceptance(t) or is_negative(t):
        return 0

    count = sum(t.count(a) for a in _ANCHOR_KEYWORDS)
    count += t.count("no me gusta")
    unique_hits = sum(1 for kw in _COUNT_KEYWORDS if kw in t)
    count += min(unique_hits, 3)
    if len(t) >= 25:
        count += 1

    if count <= 0:
        return 0
    return max(1, min(count, 4))
