from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.enums import EvaluationMode, MessageType, RiasecType
from backend.core.text import normalize_text
from backend.ml.artifacts import MODEL_VERSION, ModelArtifacts
from backend.ml.profiling import RiasecProfile, profile_from_likert_sums, profile_from_text
from backend.ml.recommender import recommend_careers
from backend.modules.chat.models import ChatMessage
from backend.modules.evaluations.models import Evaluation, EvaluationResult, Question, UserAnswer

RIASEC_CATEGORY_PREFIX = "riasec_"


def _likert_sums(session: Session, evaluation: Evaluation) -> dict[RiasecType, float]:
    statement = (
        select(Question.category, UserAnswer.selected_options)
        .join(UserAnswer.question)
        .where(
            UserAnswer.evaluation_id == evaluation.evaluation_id,
            Question.category.startswith(RIASEC_CATEGORY_PREFIX),
            UserAnswer.selected_options.is_not(None),
        )
    )
    sums = dict.fromkeys(RiasecType, 0.0)
    for category, selected_options in session.execute(statement):
        dimension = RiasecType(category.removeprefix(RIASEC_CATEGORY_PREFIX))
        sums[dimension] += float(selected_options["selected"][0])
    return sums


def _open_text(session: Session, evaluation: Evaluation) -> str:
    answers = select(UserAnswer.answer_text).where(
        UserAnswer.evaluation_id == evaluation.evaluation_id, UserAnswer.answer_text.is_not(None)
    )
    messages = (
        select(ChatMessage.content)
        .where(
            ChatMessage.session_id == evaluation.session_id,
            ChatMessage.message_type == MessageType.USER,
        )
        .order_by(ChatMessage.message_order)
    )
    texts = [*session.scalars(answers), *session.scalars(messages)]
    unique_texts = dict.fromkeys(filter(None, map(normalize_text, texts)))
    return "\n".join(unique_texts)


def _profile(session: Session, evaluation: Evaluation, artifacts: ModelArtifacts) -> RiasecProfile:
    if evaluation.evaluation_mode == EvaluationMode.OPEN:
        return profile_from_text(artifacts.pipeline, _open_text(session, evaluation))
    return profile_from_likert_sums(_likert_sums(session, evaluation))


def generate_result(
    session: Session, evaluation: Evaluation, artifacts: ModelArtifacts
) -> EvaluationResult:
    profile = _profile(session, evaluation, artifacts)
    result = evaluation.result or EvaluationResult()
    result.riasec_scores = {dimension: round(value, 4) for dimension, value in profile.items()}
    result.top_careers = [career.model_dump() for career in recommend_careers(profile, artifacts)]
    result.metrics = {
        "model_version": MODEL_VERSION,
        "source_mode": 1.0 if evaluation.evaluation_mode == EvaluationMode.OPEN else 0.0,
    }
    evaluation.result = result
    session.flush()
    return result
