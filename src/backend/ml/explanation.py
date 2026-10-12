import math
from collections.abc import Mapping, Sequence

import numpy as np

from backend.core.enums import RiasecType
from backend.core.text import join_words

DIMENSIONS = tuple(RiasecType)
CODE_LENGTH = 3

LABELS = {
    RiasecType.R: "Realista",
    RiasecType.I: "Investigador",
    RiasecType.A: "Artístico",
    RiasecType.S: "Social",
    RiasecType.E: "Emprendedor",
    RiasecType.C: "Convencional",
}

CONTRIBUTIONS = {
    RiasecType.R: "trabajo práctico",
    RiasecType.I: "investigación",
    RiasecType.A: "creatividad",
    RiasecType.S: "trato con personas",
    RiasecType.E: "liderazgo",
    RiasecType.C: "organización",
}

STUDENT_RANKS = ("tu interés más fuerte", "tu segundo interés", "tu tercer interés")
SHARED_COUNTS = {2: "dos", 3: "tres"}


def percent(score: float) -> int:
    return math.floor(score * 100 + 0.5)


def career_code(vector: np.ndarray) -> tuple[RiasecType, ...]:
    baseline = vector.min()
    ranked = sorted(range(len(DIMENSIONS)), key=lambda index: -vector[index])
    return tuple(DIMENSIONS[index] for index in ranked[:CODE_LENGTH] if vector[index] > baseline)


def student_top(profile: Mapping[RiasecType, float]) -> tuple[RiasecType, ...]:
    ranked = sorted(DIMENSIONS, key=lambda dimension: -profile[dimension])
    return tuple(dimension for dimension in ranked[:CODE_LENGTH] if profile[dimension] > 0)


def _interest(dimension: RiasecType, profile: Mapping[RiasecType, float]) -> str:
    return f"{LABELS[dimension]} ({dimension}, {percent(profile[dimension])} %)"


def _coincidence(
    shared: Sequence[RiasecType], top: Sequence[RiasecType], profile: Mapping[RiasecType, float]
) -> str:
    if len(shared) == 1:
        dimension = shared[0]
        return f"{STUDENT_RANKS[top.index(dimension)]}, {_interest(dimension, profile)}"
    interests = join_words([_interest(dimension, profile) for dimension in shared])
    return f"{SHARED_COUNTS[len(shared)]} de tus intereses más altos: {interests}"


def _meaning(shared: Sequence[RiasecType]) -> str:
    if len(shared) == 1:
        return f"En esta carrera, ese interés se traduce en {CONTRIBUTIONS[shared[0]]}."
    contributions = join_words([f"{CONTRIBUTIONS[d]} ({d})" for d in shared])
    return f"En esta carrera, eso se traduce en {contributions}."


def _missing(missing: Sequence[RiasecType], profile: Mapping[RiasecType, float]) -> str:
    profiles = join_words(
        [f"{LABELS[d]} ({d}, {CONTRIBUTIONS[d]}; en ti {percent(profile[d])} %)" for d in missing]
    )
    verb = "está" if len(missing) == 1 else "están"
    return f"También pide un perfil {profiles}, que no {verb} entre tus tres intereses más altos."


def describe_career(
    career: str, code: Sequence[RiasecType], profile: Mapping[RiasecType, float]
) -> str:
    top = student_top(profile)
    shared = [dimension for dimension in top if dimension in code]
    main = code[0]
    letters = "".join(code)

    if not top:
        return (
            f"{career} tiene código {letters}. Tu perfil no muestra intereses marcados,"
            " así que no hay una coincidencia que explicar."
        )
    if not shared:
        return (
            f"{career} tiene código {letters}, que no coincide con tus tres intereses más altos."
            " Aparece porque el equilibrio general de tu perfil se parece al de la carrera;"
            f" su interés principal, {LABELS[main]} ({main}), en ti es de"
            f" {percent(profile[main])} %."
        )

    sentences = [
        f"{career} tiene código {letters} y coincide con {_coincidence(shared, top, profile)}.",
        _meaning(shared),
    ]
    missing = [dimension for dimension in code if dimension not in shared]
    if missing:
        sentences.append(_missing(missing, profile))
    return " ".join(sentences)
