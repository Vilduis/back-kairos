import pytest
from sqlalchemy.orm import Session

from backend.core.enums import (
    ChatMode,
    CompatibleMode,
    EvaluationMode,
    MessageType,
    QuestionType,
    RiasecType,
)
from backend.ml.artifacts import MODEL_VERSION, ModelArtifacts, get_model_artifacts
from backend.ml.profiling import profile_from_text
from backend.modules.chat.models import ChatSession
from backend.modules.chat.service import add_message, ensure_evaluation
from backend.modules.evaluations.models import Question, UserAnswer
from backend.modules.evaluations.results import generate_result
from tests.conftest import UserFactory


@pytest.fixture(scope="module")
def artifacts() -> ModelArtifacts:
    return get_model_artifacts()


def _chat_session(session: Session, student_id: int, mode: ChatMode) -> ChatSession:
    chat_session = ChatSession(user_id=student_id, chat_mode=mode)
    session.add(chat_session)
    session.flush()
    return chat_session


def _likert_questions(session: Session) -> dict[RiasecType, list[Question]]:
    questions = {
        dimension: [
            Question(
                question_text=f"Pregunta {dimension}{index}",
                question_type=QuestionType.SCALE,
                category=f"riasec_{dimension}",
                compatible_modes=CompatibleMode.GUIDED,
            )
            for index in range(6)
        ]
        for dimension in RiasecType
    }
    session.add_all(q for group in questions.values() for q in group)
    session.flush()
    return questions


def test_guided_result_uses_likert_sums(
    session: Session, create_user: UserFactory, artifacts: ModelArtifacts
) -> None:
    student = create_user()
    evaluation = ensure_evaluation(
        session, _chat_session(session, student.user_id, ChatMode.GUIDED)
    )
    answers = {RiasecType.I: 5, RiasecType.R: 1}
    for dimension, questions in _likert_questions(session).items():
        for question in questions:
            session.add(
                UserAnswer(
                    evaluation_id=evaluation.evaluation_id,
                    question_id=question.question_id,
                    selected_options={"selected": [answers.get(dimension, 3)]},
                )
            )
    session.flush()

    result = generate_result(session, evaluation, artifacts)

    assert evaluation.evaluation_mode == EvaluationMode.GUIDED
    assert result.riasec_scores[RiasecType.I] == 1.0
    assert result.riasec_scores[RiasecType.R] == 0.0
    assert result.riasec_scores[RiasecType.A] == 0.5
    assert len(result.top_careers) == 3
    assert result.metrics == {"model_version": MODEL_VERSION, "source_mode": 0.0}


def test_open_result_uses_student_messages_only(
    session: Session, create_user: UserFactory, artifacts: ModelArtifacts
) -> None:
    student = create_user()
    chat_session = _chat_session(session, student.user_id, ChatMode.OPEN)
    evaluation = ensure_evaluation(session, chat_session)
    add_message(session, chat_session, MessageType.BOT, "¿Qué te gusta hacer?")
    add_message(session, chat_session, MessageType.USER, "Me gusta programar y las matemáticas")
    add_message(session, chat_session, MessageType.USER, "me gusta programar y las matematicas")
    session.flush()

    result = generate_result(session, evaluation, artifacts)

    expected = profile_from_text(artifacts.pipeline, "me gusta programar y las matematicas")
    assert result.riasec_scores == {key: round(value, 4) for key, value in expected.items()}
    assert result.metrics["source_mode"] == 1.0


def test_regenerating_updates_the_same_result(
    session: Session, create_user: UserFactory, artifacts: ModelArtifacts
) -> None:
    student = create_user()
    evaluation = ensure_evaluation(session, _chat_session(session, student.user_id, ChatMode.OPEN))

    first = generate_result(session, evaluation, artifacts)
    second = generate_result(session, evaluation, artifacts)

    assert first.result_id == second.result_id


def test_messages_get_consecutive_order(session: Session, create_user: UserFactory) -> None:
    student = create_user()
    chat_session = _chat_session(session, student.user_id, ChatMode.OPEN)

    orders = []
    for text in ("uno", "dos", "tres"):
        orders.append(add_message(session, chat_session, MessageType.USER, text).message_order)
        session.flush()

    assert orders == [1, 2, 3]
