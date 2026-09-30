from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.enums import ChatMode, EvaluationMode, MessageType
from backend.core.exceptions import NotFoundError
from backend.modules.chat.models import ChatMessage, ChatSession
from backend.modules.evaluations.models import Evaluation


def get_student_session(
    session: Session, session_id: int, student_id: int, mode: ChatMode | None = None
) -> ChatSession:
    chat_session = session.get(ChatSession, session_id)
    if chat_session is None or chat_session.user_id != student_id:
        raise NotFoundError("Sesión de chat no encontrada")
    if mode is not None and chat_session.chat_mode != mode:
        mode_label = "guiado" if mode == ChatMode.GUIDED else "abierto"
        raise NotFoundError(f"Sesión de chat {mode_label} no encontrada")
    return chat_session


def touch(chat_session: ChatSession) -> None:
    chat_session.last_activity = datetime.now(UTC)


def list_messages(session: Session, chat_session: ChatSession) -> Sequence[ChatMessage]:
    statement = (
        select(ChatMessage)
        .where(ChatMessage.session_id == chat_session.session_id)
        .order_by(ChatMessage.message_order)
    )
    return session.scalars(statement).all()


def add_message(
    session: Session, chat_session: ChatSession, message_type: MessageType, content: str
) -> ChatMessage:
    last_order = session.scalar(
        select(func.max(ChatMessage.message_order)).where(
            ChatMessage.session_id == chat_session.session_id
        )
    )
    message = ChatMessage(
        session_id=chat_session.session_id,
        message_type=message_type,
        content=content,
        message_order=(last_order or 0) + 1,
    )
    session.add(message)
    touch(chat_session)
    return message


def ensure_evaluation(session: Session, chat_session: ChatSession) -> Evaluation:
    if chat_session.evaluation is None:
        mode = (
            EvaluationMode.OPEN
            if chat_session.chat_mode == ChatMode.OPEN
            else EvaluationMode.GUIDED
        )
        chat_session.evaluation = Evaluation(user_id=chat_session.user_id, evaluation_mode=mode)
        session.flush()
    return chat_session.evaluation
