from fastapi import APIRouter

from backend.api.deps import ModelArtifactsDep
from backend.modules.recommendation import service
from backend.modules.recommendation.schemas import (
    ChatTextInput,
    RecommendationResponse,
    RiasecTestInput,
)

router = APIRouter(tags=["recommendation"])


@router.post("/recomendar-por-test")
def recommend_from_test(
    scores: RiasecTestInput, artifacts: ModelArtifactsDep
) -> RecommendationResponse:
    return service.recommend_from_test(scores, artifacts)


@router.post("/recomendar-por-chat")
def recommend_from_text(
    data: ChatTextInput, artifacts: ModelArtifactsDep
) -> RecommendationResponse:
    return service.recommend_from_text(data.texto, artifacts)
