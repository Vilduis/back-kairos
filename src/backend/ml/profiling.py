from collections.abc import Mapping

import numpy as np
from sklearn.pipeline import Pipeline

from backend.core.enums import RiasecType
from backend.core.text import normalize_text

type RiasecProfile = dict[RiasecType, float]

ITEMS_PER_DIMENSION = 6
LIKERT_MIN, LIKERT_MAX = 1, 5


def empty_profile() -> RiasecProfile:
    return dict.fromkeys(RiasecType, 0.0)


def to_unit_scale(scale_1_to_5: float) -> float:
    return float(np.clip((scale_1_to_5 - LIKERT_MIN) / (LIKERT_MAX - LIKERT_MIN), 0.0, 1.0))


def to_likert_scale(unit: float) -> float:
    return round(float(np.clip(unit * (LIKERT_MAX - LIKERT_MIN) + LIKERT_MIN, 1.0, 5.0)), 1)


def profile_from_likert_sums(sums: Mapping[RiasecType, float]) -> RiasecProfile:
    lowest = ITEMS_PER_DIMENSION * LIKERT_MIN
    highest = ITEMS_PER_DIMENSION * LIKERT_MAX
    # El paso intermedio por la escala 1-5 redondeada a un decimal replica el cálculo con
    # el que se generaron los resultados publicados; omitirlo cambiaría los puntajes.
    return {
        dimension: to_unit_scale(
            to_likert_scale((sums.get(dimension, 0.0) - lowest) / (highest - lowest))
        )
        for dimension in RiasecType
    }


def profile_from_text(pipeline: Pipeline, text: str) -> RiasecProfile:
    normalized = normalize_text(text)
    if not normalized:
        return empty_profile()
    prediction = np.clip(pipeline.predict([normalized])[0], 0.0, 1.0)
    return {
        dimension: float(value) for dimension, value in zip(RiasecType, prediction, strict=True)
    }
