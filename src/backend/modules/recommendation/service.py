from backend.core.enums import RiasecType
from backend.ml.artifacts import ModelArtifacts
from backend.ml.profiling import profile_from_text, to_likert_scale, to_unit_scale
from backend.ml.recommender import recommend_careers
from backend.modules.recommendation.schemas import RecommendationResponse, RiasecTestInput


def recommend_from_test(
    scores: RiasecTestInput, artifacts: ModelArtifacts
) -> RecommendationResponse:
    likert_profile = {dimension: round(getattr(scores, dimension), 1) for dimension in RiasecType}
    unit_profile = {dimension: to_unit_scale(value) for dimension, value in likert_profile.items()}
    return RecommendationResponse(
        riasec_profile=likert_profile,
        top3_careers=recommend_careers(unit_profile, artifacts),
    )


def recommend_from_text(text: str, artifacts: ModelArtifacts) -> RecommendationResponse:
    unit_profile = profile_from_text(artifacts.pipeline, text)
    return RecommendationResponse(
        riasec_profile={
            dimension: to_likert_scale(value) for dimension, value in unit_profile.items()
        },
        top3_careers=recommend_careers(unit_profile, artifacts),
    )
