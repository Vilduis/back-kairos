from collections.abc import Sequence

from sqlalchemy.orm import Session

from backend.conversation.assistant import (
    ChatTurn,
    generate_closing_message,
    generate_open_followup,
)
from backend.conversation.heuristics import count_signals, is_acceptance
from backend.core.enums import ChatMode, ConversationStage, MessageType
from backend.modules.chat.models import ChatMessage, ChatSession
from backend.modules.chat.schemas import ChatMessageRead, OpenTurnResponse
from backend.modules.chat.service import add_message, get_student_session, list_messages, touch
from backend.modules.users.models import User

RESULTS_CONFIRMED_DETAIL = "El estudiante confirmó ver resultados. Generando..."
MIN_USER_MESSAGES = 7
MIN_SIGNALS = 5


def _total_signals(user_texts: Sequence[str]) -> int:
    return sum(count_signals(text) for text in user_texts)


def _reply(
    session: Session, chat_session: ChatSession, content: str, *, awaiting_confirmation: bool
) -> OpenTurnResponse:
    message = add_message(session, chat_session, MessageType.BOT, content)
    session.commit()
    session.refresh(message)
    return OpenTurnResponse(
        bot_message=ChatMessageRead.model_validate(message),
        awaiting_confirmation=awaiting_confirmation or None,
    )


def _followup(
    session: Session,
    chat_session: ChatSession,
    student: User,
    messages: Sequence[ChatMessage],
    user_texts: list[str],
) -> OpenTurnResponse:
    history = [ChatTurn(role=m.message_type, content=m.content) for m in messages]
    student_name = student.full_name if not user_texts else None
    text = generate_open_followup(user_texts, history, student_name)
    return _reply(session, chat_session, text, awaiting_confirmation=False)


def next_open_turn(session: Session, student: User, session_id: int) -> OpenTurnResponse:
    chat_session = get_student_session(session, session_id, student.user_id, mode=ChatMode.OPEN)
    messages = list_messages(session, chat_session)
    user_texts = [m.content for m in messages if m.message_type == MessageType.USER]
    last_text = user_texts[-1].strip() if user_texts else ""
    stage = chat_session.conversation_stage
    confirming = stage == ConversationStage.CONFIRM_RESULTS
    enough_messages = len(user_texts) >= MIN_USER_MESSAGES
    accepted = is_acceptance(last_text)

    if accepted and (confirming or (enough_messages and _total_signals(user_texts) >= MIN_SIGNALS)):
        chat_session.conversation_stage = ConversationStage.RESULTS
        touch(chat_session)
        session.commit()
        return OpenTurnResponse(detail=RESULTS_CONFIRMED_DETAIL)

    if accepted or confirming:
        chat_session.conversation_stage = ConversationStage.COLLECTING
    elif enough_messages and stage != ConversationStage.RESULTS:
        chat_session.conversation_stage = ConversationStage.CONFIRM_RESULTS
        closing = generate_closing_message(user_texts, student.full_name)
        return _reply(session, chat_session, closing, awaiting_confirmation=True)

    return _followup(session, chat_session, student, messages, user_texts)
