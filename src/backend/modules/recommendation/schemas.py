from pydantic import BaseModel, Field

from backend.core.enums import RiasecType
from backend.ml.recommender import CareerRecommendation

Likert = Field(ge=1.0, le=5.0)


class RiasecTestInput(BaseModel):
    R: float = Likert
    I: float = Likert  # noqa: E741
    A: float = Likert
    S: float = Likert
    E: float = Likert
    C: float = Likert


class ChatTextInput(BaseModel):
    texto: str = Field(min_length=1)


class RecommendationResponse(BaseModel):
    riasec_profile: dict[RiasecType, float]
    top3_careers: list[CareerRecommendation]
