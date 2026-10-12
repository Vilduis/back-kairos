from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from pydantic import BaseModel
from sklearn.metrics.pairwise import cosine_similarity

from backend.core.enums import RiasecType
from backend.ml.artifacts import ModelArtifacts
from backend.ml.explanation import DIMENSIONS, career_code, describe_career
from backend.ml.profiling import RiasecProfile


class CareerRecommendation(BaseModel):
    career: str
    score: float
    description: str
    faculty: str


def recommend_careers(
    profile: RiasecProfile, artifacts: ModelArtifacts, top_n: int = 3
) -> list[CareerRecommendation]:
    user_vector = np.array([profile[dimension] for dimension in DIMENSIONS], dtype=float)
    similarities = cosine_similarity(user_vector.reshape(1, -1), artifacts.career_vectors)[0]
    # Varias carreras comparten vector RIASEC y empatan; el orden estable por posición en el
    # catálogo hace que el Top-N sea reproducible entre versiones de numpy.
    ranking = np.argsort(-similarities, kind="stable")[:top_n]
    return [
        CareerRecommendation(
            career=artifacts.careers[index].name,
            score=round(float(similarities[index]), 2),
            description=describe_career(
                artifacts.careers[index].name,
                career_code(artifacts.career_vectors[index]),
                profile,
            ),
            faculty=artifacts.careers[index].faculty,
        )
        for index in ranking
    ]


def explain_saved_careers(
    scores: Mapping[str, float], careers: Sequence[Mapping[str, Any]], artifacts: ModelArtifacts
) -> list[dict[str, Any]]:
    profile = {dimension: float(scores.get(dimension, 0.0)) for dimension in RiasecType}
    vectors = {
        career.name: vector
        for career, vector in zip(artifacts.careers, artifacts.career_vectors, strict=True)
    }
    return [
        {**career, "description": describe_career(name, career_code(vectors[name]), profile)}
        if (name := str(career.get("career", "")).strip()) in vectors
        else dict(career)
        for career in careers
    ]
