import zlib
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, auto

from backend.conversation.heuristics import (
    is_greeting,
    is_substantive_signal,
    is_task_request,
)
from backend.core.enums import MessageType
from backend.core.text import normalize_text
from backend.integrations.llm import generate_text


@dataclass(frozen=True)
class ChatTurn:
    role: MessageType
    content: str


class FollowupPhase(Enum):
    OPENING = auto()
    DEEPENING = auto()
    CONTEXT = auto()
    VALUES = auto()


FOLLOWUP_SYSTEM_INSTRUCTION = (
    "Eres Kairos, orientador vocacional cálido y cercano, en español latinoamericano, "
    "especializado en estudiantes de 17-19 años (5to de secundaria).\n"
    "{name_instruction}"
    "Tu único objetivo es recolectar señales vocacionales útiles: gustos concretos, "
    "habilidades, fortalezas y contexto preferido de trabajo.\n\n"
    "REGLAS ESTRICTAS (siempre):\n"
    "- Responde con máximo 2 oraciones: primero un reconocimiento breve y concreto "
    "(5-8 palabras) de algo específico que dijo el estudiante, luego UNA sola pregunta.\n"
    "- El reconocimiento debe ser específico, NO genérico "
    "(prohibido: 'Qué interesante', 'Genial', 'Muy bien').\n"
    "- La pregunta debe tener máximo 15 palabras.\n"
    "- NUNCA repitas un tema que ya apareció en el historial.\n"
    "- NUNCA empieces con 'Y con lo que comentaste' ni 'Teniendo en cuenta que comentaste'.\n"
    "- Varía el inicio de cada respuesta; no empieces siempre de la misma forma.\n"
    "- Evita preguntas de doble opción largas.\n"
    "- Responde SOLO con el mensaje final. Sin comillas, sin explicaciones, sin meta-comentarios."
)

FOLLOWUP_INTENTS = {
    FollowupPhase.OPENING: (
        "El último mensaje es un saludo o presentación inicial. "
        "Responde con una pregunta amable para arrancar: pide gustos, habilidades o fortalezas "
        "con uno o dos ejemplos concretos."
    ),
    FollowupPhase.DEEPENING: (
        "El estudiante compartió 1-2 señales vocacionales. Formula una pregunta que profundice "
        "en lo que dijo: qué parte disfruta más, qué lo motiva dentro de ese tema, "
        "o pide un ejemplo concreto."
    ),
    FollowupPhase.CONTEXT: (
        "Ya hay 3-4 señales sobre gustos y habilidades. Explora el contexto de trabajo preferido: "
        "¿solo o en equipo?, ¿ambiente académico, empresa o startup?, "
        "¿más creativo o más analítico? Conéctalo con algo que el estudiante ya mencionó."
    ),
    FollowupPhase.VALUES: (
        "Hay muchas señales. Pide un matiz final sobre valores o condiciones de trabajo "
        "(impacto social, estabilidad, innovación) basándote en lo que ya compartió."
    ),
}
TASK_FOLLOWUP_INTENTS = {
    FollowupPhase.DEEPENING: (
        "El estudiante quiere analizar algo. Pide un ejemplo concreto de un reto o ejercicio "
        "que le haya gustado y qué parte fue clave. Añade un micro-elogio suave."
    ),
}

FALLBACK_QUESTIONS = {
    FollowupPhase.OPENING: (
        "¿Qué actividades disfrutas y en qué te sientes fuerte?",
        "¿Qué materias o temas te llaman más la atención?",
        "¿Qué haces en tu tiempo libre que te salga de forma natural?",
    ),
    FollowupPhase.DEEPENING: (
        "¿Qué parte disfrutas más: resolver problemas, analizar datos o crear cosas?",
        "¿Hay algún proyecto donde hayas dado lo mejor de ti?",
        "¿Qué se te da mejor: diseñar ideas, calcular o comunicarlas?",
        "¿Cuándo dices 'esto sí me gusta'? ¿Qué sueles estar haciendo?",
    ),
    FollowupPhase.CONTEXT: (
        "¿Prefieres trabajar solo o en equipo?",
        "¿Te imaginas en una empresa grande, startup o investigando?",
        "¿Buscas algo más creativo o más analítico en tu trabajo ideal?",
    ),
    FollowupPhase.VALUES: (
        "¿Qué te importa más: impacto social, estabilidad o innovar?",
        "¿Hay algo que no harías aunque pagara bien?",
        "¿Qué condición de trabajo sería innegociable para ti?",
    ),
}
TASK_FALLBACK_QUESTIONS = {
    FollowupPhase.DEEPENING: (
        "¿Qué ejercicio o reto recuerdas que te gustó resolver?",
        "¿Qué tipo de problema te resulta más interesante atacar?",
    ),
    FollowupPhase.CONTEXT: (
        "¿Qué tipo de problema disfrutas resolver: lógica, datos o diseño?",
        "¿Prefieres trabajar con números, personas o ideas?",
    ),
}

CLOSING_PROMPT = (
    "Eres Kairos, orientador vocacional cálido y cercano, en español latinoamericano.\n"
    "{name_instruction}"
    "El estudiante de 5to de secundaria compartió lo siguiente en la conversación:\n"
    "{summary}\n\n"
    "Escribe UN mensaje de cierre breve (máx. 35 palabras) que:\n"
    "1. Empiece con el nombre del estudiante si lo tienes.\n"
    "2. Mencione 2 o 3 temas concretos que compartió (ej: programación, IA, matemáticas).\n"
    "3. Diga que ya tienes suficiente información para estimar su perfil.\n"
    "4. Pregunte si quiere ver sus resultados.\n"
    "5. Use un tono cálido y motivador.\n"
    "Ejemplo: '¡{example_name}, con todo lo que me contaste sobre programación e IA ya tengo "
    "tu perfil! ¿Quieres ver tus carreras recomendadas? Responde sí o no.'\n"
    "Responde SOLO con el mensaje, sin comillas."
)

# Las claves se comparan contra el texto normalizado; el orden decide qué temas se citan.
CLOSING_TOPICS = (
    ("programar", "programación"),
    ("programacion", "programación"),
    ("inteligencia artificial", "IA"),
    ("machine learning", "machine learning"),
    ("ia ", "IA"),
    ("matematicas", "matemáticas"),
    ("ciencia", "ciencia"),
    ("tecnologia", "tecnología"),
    ("datos", "ciencia de datos"),
    ("diseñar", "diseño"),
    ("arte", "arte"),
    ("musica", "música"),
    ("deporte", "deporte"),
    ("investigar", "investigación"),
    ("analizar", "análisis"),
)
MAX_CLOSING_TOPICS = 3


def _first_name(full_name: str | None) -> str:
    parts = (full_name or "").split()
    return parts[0] if parts else ""


def _followup_phase(last_text: str, user_texts: Sequence[str]) -> FollowupPhase:
    signal_messages = sum(1 for text in user_texts if is_substantive_signal(text))
    if is_greeting(last_text) or signal_messages == 0:
        return FollowupPhase.OPENING
    if signal_messages <= 2:
        return FollowupPhase.DEEPENING
    if signal_messages <= 4:
        return FollowupPhase.CONTEXT
    return FollowupPhase.VALUES


def _format_history(user_texts: Sequence[str], history: Sequence[ChatTurn]) -> str:
    if not history:
        return "\n".join(f"Estudiante: {text}" for text in user_texts)
    return "\n".join(
        f"{'Estudiante' if turn.role == MessageType.USER else 'Kairos'}: {turn.content.strip()}"
        for turn in history
    )


def _fallback_question(
    phase: FollowupPhase, task_request: bool, last_text: str, history: Sequence[ChatTurn]
) -> str:
    options = (task_request and TASK_FALLBACK_QUESTIONS.get(phase)) or FALLBACK_QUESTIONS[phase]
    asked = {turn.content.strip() for turn in history if turn.role == MessageType.BOT}
    available = [option for option in options if option not in asked] or list(options)
    # crc32 en lugar de hash(): el hash de str cambia entre procesos y la rotación debe ser
    # reproducible.
    return available[zlib.crc32(last_text.encode()) % len(available)]


def generate_open_followup(
    user_texts: Sequence[str],
    history: Sequence[ChatTurn] = (),
    student_name: str | None = None,
) -> str:
    last_text = user_texts[-1].strip() if user_texts else ""
    phase = _followup_phase(last_text, user_texts)
    task_request = is_task_request(last_text)

    first_name = _first_name(student_name)
    name_instruction = (
        f"El nombre del estudiante es {first_name}. Úsalo naturalmente cuando sea apropiado.\n"
        if first_name
        else ""
    )
    intent = (task_request and TASK_FOLLOWUP_INTENTS.get(phase)) or FOLLOWUP_INTENTS[phase]
    contents = (
        f"### Historial de conversación:\n{_format_history(user_texts, history)}\n\n"
        f'### Último mensaje del estudiante:\n"{last_text}"\n\n'
        f"### Tu tarea para este turno:\n{intent}"
    )
    generated = generate_text(
        contents, FOLLOWUP_SYSTEM_INSTRUCTION.format(name_instruction=name_instruction)
    )
    return generated or _fallback_question(phase, task_request, last_text, history)


def _closing_topics(texts: Sequence[str]) -> list[str]:
    full_text = normalize_text(" ".join(texts))
    topics: list[str] = []
    for keyword, label in CLOSING_TOPICS:
        if keyword in full_text and label not in topics:
            topics.append(label)
        if len(topics) >= MAX_CLOSING_TOPICS:
            break
    return topics


def _join_topics(topics: Sequence[str]) -> str:
    if len(topics) == 1:
        return topics[0]
    return f"{', '.join(topics[:-1])} y {topics[-1]}"


def _fallback_closing(texts: Sequence[str], first_name: str) -> str:
    name_prefix = f"{first_name}, " if first_name else ""
    topics = _closing_topics(texts)
    if topics:
        return (
            f"¡{name_prefix}con lo que me contaste sobre {_join_topics(topics)} ya tengo "
            "suficiente para estimar tu perfil. ¿Te muestro tus carreras recomendadas? "
            "Responde 'sí' o 'no'."
        )
    return (
        f"¡{name_prefix}ya tengo suficiente información para estimar tu perfil vocacional. "
        "¿Te muestro los resultados ahora? Responde 'sí' para verlos o 'no' para seguir "
        "conversando."
    )


def generate_closing_message(user_texts: Sequence[str], student_name: str | None = None) -> str:
    texts = [text.strip() for text in user_texts if text.strip()]
    first_name = _first_name(student_name)
    if not texts:
        greeting = f"¡{first_name}, ya tengo" if first_name else "¡Ya tengo"
        return (
            f"{greeting} suficiente información para estimar tu perfil. "
            "¿Te muestro los resultados ahora? Responde 'sí' para verlos o 'no' para seguir."
        )

    name_instruction = (
        f"El nombre del estudiante es {first_name}. Úsalo al inicio del mensaje.\n"
        if first_name
        else ""
    )
    prompt = CLOSING_PROMPT.format(
        name_instruction=name_instruction,
        summary="\n".join(f"- {text}" for text in texts),
        example_name=first_name or "Ana",
    )
    return generate_text(prompt) or _fallback_closing(texts, first_name)
