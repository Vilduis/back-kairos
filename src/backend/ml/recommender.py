import numpy as np
from pydantic import BaseModel
from sklearn.metrics.pairwise import cosine_similarity

from backend.core.enums import RiasecType
from backend.ml.artifacts import ModelArtifacts
from backend.ml.profiling import RiasecProfile

DIMENSIONS = tuple(RiasecType)

LABELS = {
    RiasecType.R: "Realista",
    RiasecType.I: "Investigador",
    RiasecType.A: "Artístico",
    RiasecType.S: "Social",
    RiasecType.E: "Emprendedor",
    RiasecType.C: "Convencional",
}

TRAITS = {
    RiasecType.R: "proyectos prácticos y resultados tangibles",
    RiasecType.I: "análisis y resolución de problemas complejos",
    RiasecType.A: "creación y diseño de soluciones creativas",
    RiasecType.S: "comunicación y trabajo colaborativo",
    RiasecType.E: "liderazgo, negociación y dirección de iniciativas",
    RiasecType.C: "organización, planificación y seguimiento de procesos",
}


class CareerRecommendation(BaseModel):
    career: str
    score: float
    description: str
    faculty: str


def _dominant(vector: np.ndarray, count: int = 2) -> list[RiasecType]:
    return [DIMENSIONS[index] for index in np.argsort(vector)[::-1][:count]]


def _label(dimension: RiasecType) -> str:
    return f"{LABELS[dimension]} ({dimension})"


def _describe(career: str, career_vector: np.ndarray, user_top: list[RiasecType]) -> str:
    first, second = _dominant(career_vector)
    return (
        f"Se alinea con tus intereses {_label(user_top[0])} y {_label(user_top[1])}."
        f" En {career}, el enfoque {_label(first)} favorece {TRAITS[first]}."
        f" También aporta {TRAITS[second]} desde {_label(second)}."
    )


def recommend_careers(
    profile: RiasecProfile, artifacts: ModelArtifacts, top_n: int = 3
) -> list[CareerRecommendation]:
    user_vector = np.array([profile[dimension] for dimension in DIMENSIONS], dtype=float)
    similarities = cosine_similarity(user_vector.reshape(1, -1), artifacts.career_vectors)[0]
    user_top = _dominant(user_vector)
    # Varias carreras comparten vector RIASEC y empatan; el orden estable por posición en el
    # catálogo hace que el Top-N sea reproducible entre versiones de numpy.
    ranking = np.argsort(-similarities, kind="stable")[:top_n]
    return [
        CareerRecommendation(
            career=artifacts.careers[index].name,
            score=round(float(similarities[index]), 2),
            description=_describe(
                artifacts.careers[index].name, artifacts.career_vectors[index], user_top
            ),
            faculty=artifacts.careers[index].faculty,
        )
        for index in ranking
    ]
