from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.enums import (
    ChatMode,
    CompatibleMode,
    ConversationStage,
    EvaluationStatus,
    MessageType,
    SessionStatus,
)
from backend.core.exceptions import NotFoundError
from backend.ml.artifacts import ModelArtifacts
from backend.modules.chat.models import ChatMessage, ChatSession
from backend.modules.chat.schemas import (
    ChatMessageCreate,
    ChatSessionCreate,
    CompletionResponse,
    GuidedProgress,
    QuestionRead,
    SessionAnswerCreate,
)
from backend.modules.chat.service import (
    add_message,
    ensure_evaluation,
    get_student_session,
    list_messages,
    touch,
)
from backend.modules.evaluations.models import EvaluationResult, Question, UserAnswer
from backend.modules.evaluations.results import generate_result
from backend.modules.evaluations.service import EVALUATION_NOT_FOUND, get_result


def create_session(session: Session, student_id: int, data: ChatSessionCreate) -> ChatSession:
    chat_session = ChatSession(
        user_id=student_id, chat_mode=data.chat_mode, conversation_stage=data.conversation_stage
    )
    session.add(chat_session)
    session.commit()
    return chat_session


def list_sessions(session: Session, student_id: int) -> Sequence[ChatSession]:
    statement = (
        select(ChatSession)
        .where(ChatSession.user_id == student_id)
        .order_by(ChatSession.session_id)
    )
    return session.scalars(statement).all()


def delete_session(session: Session, session_id: int, student_id: int) -> None:
    session.delete(get_student_session(session, session_id, student_id))
    session.commit()


def add_student_message(session: Session, student_id: int, data: ChatMessageCreate) -> ChatMessage:
    chat_session = get_student_session(session, data.session_id, student_id)
    message = add_message(session, chat_session, MessageType.USER, data.content)
    session.commit()
    return message


def list_student_messages(
    session: Session, session_id: int, student_id: int
) -> Sequence[ChatMessage]:
    return list_messages(session, get_student_session(session, session_id, student_id))


def _guided_questions(session: Session) -> Sequence[Question]:
    statement = (
        select(Question)
        .where(Question.compatible_modes.in_((CompatibleMode.GUIDED, CompatibleMode.BOTH)))
        .order_by(Question.display_order, Question.question_id)
    )
    return session.scalars(statement).all()


def _answered_question_ids(session: Session, chat_session: ChatSession) -> set[int]:
    if chat_session.evaluation is None:
        return set()
    statement = select(UserAnswer.question_id).where(
        UserAnswer.evaluation_id == chat_session.evaluation.evaluation_id
    )
    return set(session.scalars(statement))


def _guided_progress(session: Session, answered_ids: set[int]) -> GuidedProgress:
    questions = _guided_questions(session)
    if not questions:
        raise NotFoundError("No hay preguntas configuradas")
    pending = next((q for q in questions if q.question_id not in answered_ids), None)
    return GuidedProgress(
        completed=pending is None,
        question=QuestionRead.model_validate(pending) if pending else None,
        total=len(questions),
        answered=sum(q.question_id in answered_ids for q in questions),
    )


def first_guided_question(session: Session) -> GuidedProgress:
    return _guided_progress(session, answered_ids=set())


def next_guided_question(session: Session, session_id: int, student_id: int) -> GuidedProgress:
    chat_session = get_student_session(session, session_id, student_id, mode=ChatMode.GUIDED)
    progress = _guided_progress(session, _answered_question_ids(session, chat_session))
    if progress.question is not None:
        chat_session.current_question_id = progress.question.question_id
        session.commit()
    return progress


def save_answer(
    session: Session, session_id: int, student_id: int, data: SessionAnswerCreate
) -> UserAnswer:
    chat_session = get_student_session(session, session_id, student_id)
    if session.get(Question, data.question_id) is None:
        raise NotFoundError("Pregunta no encontrada")
    evaluation = ensure_evaluation(session, chat_session)
    answer = session.scalar(
        select(UserAnswer).where(
            UserAnswer.evaluation_id == evaluation.evaluation_id,
            UserAnswer.question_id == data.question_id,
        )
    ) or UserAnswer(evaluation_id=evaluation.evaluation_id, question_id=data.question_id)
    answer.answer_text = data.answer_text
    answer.selected_options = data.selected_options.model_dump() if data.selected_options else None
    session.add(answer)
    touch(chat_session)
    session.commit()
    return answer


def complete_session(
    session: Session, session_id: int, student_id: int, artifacts: ModelArtifacts
) -> CompletionResponse:
    chat_session = get_student_session(session, session_id, student_id)
    evaluation = ensure_evaluation(session, chat_session)
    result = generate_result(session, evaluation, artifacts)
    evaluation.status = EvaluationStatus.COMPLETED
    evaluation.progress = 1.0
    evaluation.completed_at = datetime.now(UTC)
    chat_session.status = SessionStatus.COMPLETED
    chat_session.conversation_stage = ConversationStage.RESULTS
    touch(chat_session)
    session.commit()
    return CompletionResponse(
        detail="Evaluación completada",
        evaluation_id=evaluation.evaluation_id,
        result_id=result.result_id,
    )


def get_session_result(session: Session, session_id: int, student_id: int) -> EvaluationResult:
    chat_session = get_student_session(session, session_id, student_id)
    if chat_session.evaluation is None:
        raise NotFoundError(EVALUATION_NOT_FOUND)
    return get_result(chat_session.evaluation)
