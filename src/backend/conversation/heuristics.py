from backend.core.text import normalize_text

GREETINGS = (
    "hola",
    "holi",
    "buenas",
    "buen dia",
    "buenos dias",
    "buenas tardes",
    "buenas noches",
    "hey",
    "que tal",
    "saludos",
)
SHORT_YES = frozenset({"si", "yes", "ok", "okay", "dale", "claro"})
RESULT_VERBS = frozenset(
    {
        "ver",
        "mostrar",
        "muestrame",
        "dame",
        "dar",
        "entregar",
        "obtener",
        "tener",
        "quiero",
        "necesito",
        "podrias",
        "puedes",
    }
)
RESULT_NOUNS = frozenset({"resultado", "resultados"})
RESULT_REQUESTS = (
    "verlos",
    "ver resultados",
    "mostrar resultados",
    "quiero ver",
    "quiero mis resultados",
    "mi resultado",
    "dame mi resultado",
    "darme el resultado",
    "darme mi resultado",
)
NEGATIVE_PHRASES = ("no aun", "todavia no", "prefiero seguir", "seguir conversando")
TASK_CUES = (
    "puedes",
    "podrias",
    "ayuda",
    "analizar",
    "resolver ejercicio",
    "responder ejercicio",
    "explicar",
    "explicame",
    "como resolver",
)

ANCHOR_KEYWORDS = (
    "me gusta",
    "me encanta",
    "prefiero",
    "disfruto",
    "me interesa",
    "me atrae",
    "soy bueno",
    "se me da",
    "me vacila",
    "me motiva",
    "me apasiona",
    "me llama",
)
TOPIC_KEYWORDS = (
    "habilidad",
    "fortaleza",
    "crear",
    "diseñar",
    "dibujar",
    "pintar",
    "programar",
    "investigar",
    "analizar",
    "analizar datos",
    "enseñar",
    "comunicar",
    "organizar",
    "liderar",
    "colaborar",
    "arte",
    "musica",
    "deporte",
    "tecnologia",
    "ciencia",
    "matematicas",
    "numeros",
    "negocios",
    "marketing",
    "cultura",
    "escribir",
    "acertijos",
    "rompecabezas",
    "ayudar",
)
SIGNAL_KEYWORDS = (
    *ANCHOR_KEYWORDS,
    *TOPIC_KEYWORDS,
    "fan",
    "aficion",
    "pasiones",
    "paisajes",
    "historias",
)
MAX_TOPIC_HITS = 3
MAX_SIGNALS_PER_MESSAGE = 4


def is_greeting(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return False
    return len(normalized) <= 5 or (len(normalized) <= 40 and normalized.startswith(GREETINGS))


def is_acceptance(text: str) -> bool:
    normalized = normalize_text(text)
    words = set(normalized.split())
    if words & SHORT_YES or (words & RESULT_VERBS and words & RESULT_NOUNS):
        return True
    return any(request in normalized for request in RESULT_REQUESTS)


def is_negative(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return False
    if any(phrase in normalized for phrase in NEGATIVE_PHRASES):
        return True
    # Un "no" solo cuenta en respuestas cortas: "no me gusta la química" es una señal
    # vocacional, no un rechazo.
    tokens = normalized.split()
    return len(tokens) <= 3 and tokens[0] == "no"


def is_task_request(text: str) -> bool:
    normalized = normalize_text(text)
    return any(cue in normalized for cue in TASK_CUES)


def _is_filler(normalized: str) -> bool:
    return is_greeting(normalized) or is_acceptance(normalized) or is_negative(normalized)


def is_substantive_signal(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized or _is_filler(normalized):
        return False
    return len(normalized) >= 15 or any(keyword in normalized for keyword in SIGNAL_KEYWORDS)


def count_signals(text: str) -> int:
    normalized = normalize_text(text)
    if not normalized or _is_filler(normalized):
        return 0
    count = sum(normalized.count(anchor) for anchor in ANCHOR_KEYWORDS)
    count += normalized.count("no me gusta")
    topic_hits = sum(1 for topic in TOPIC_KEYWORDS if topic in normalized)
    count += min(topic_hits, MAX_TOPIC_HITS)
    if len(normalized) >= 25:
        count += 1
    return min(count, MAX_SIGNALS_PER_MESSAGE)
