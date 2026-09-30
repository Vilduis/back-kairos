from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.conversation.assistant import FALLBACK_QUESTIONS, FollowupPhase
from backend.core.enums import ChatMode, ConversationStage, MessageType, UserRole
from backend.modules.chat import open_flow
from backend.modules.chat.models import ChatMessage, ChatSession
from backend.modules.chat.open_flow import RESULTS_CONFIRMED_DETAIL
from backend.modules.chat.service import add_message
from backend.modules.users.models import User
from tests.conftest import UserFactory, auth_headers

SIGNAL_MESSAGES = [
    "me gusta programar videojuegos",
    "me encanta la matemática",
    "disfruto dibujar paisajes",
    "soy bueno organizando eventos",
    "me interesa la ciencia",
    "me apasiona la tecnología",
    "me gusta el arte digital",
]
BOT_QUESTION = "¿Qué te gusta?"


@pytest.fixture
def student(create_user: UserFactory) -> User:
    return create_user()


def _open_session(
    session: Session,
    student: User,
    user_texts: list[str],
    stage: ConversationStage = ConversationStage.COLLECTING,
    mode: ChatMode = ChatMode.OPEN,
) -> ChatSession:
    chat_session = ChatSession(user_id=student.user_id, chat_mode=mode, conversation_stage=stage)
    session.add(chat_session)
    session.flush()
    for text in user_texts:
        add_message(session, chat_session, MessageType.BOT, BOT_QUESTION)
        add_message(session, chat_session, MessageType.USER, text)
    session.flush()
    return chat_session


def _next(client: TestClient, user: User, chat_session: ChatSession) -> Response:
    return client.post(
        f"/chat/sessions/{chat_session.session_id}/open/next", headers=auth_headers(user)
    )


def _bot_messages(session: Session, chat_session: ChatSession) -> list[str]:
    return list(
        session.scalars(
            select(ChatMessage.content)
            .where(
                ChatMessage.session_id == chat_session.session_id,
                ChatMessage.message_type == MessageType.BOT,
            )
            .order_by(ChatMessage.message_order)
        )
    )


def test_first_turn_returns_opening_question(
    client: TestClient, session: Session, student: User
) -> None:
    chat_session = _open_session(session, student, [], ConversationStage.WELCOME)

    response = _next(client, student, chat_session)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"bot_message"}
    assert body["bot_message"]["content"] in FALLBACK_QUESTIONS[FollowupPhase.OPENING]
    assert body["bot_message"]["message_type"] == "bot"
    assert body["bot_message"]["message_order"] == 1
    assert chat_session.conversation_stage == ConversationStage.WELCOME
    assert _bot_messages(session, chat_session) == [body["bot_message"]["content"]]


def test_confirmation_accepted_moves_to_results(
    client: TestClient, session: Session, student: User
) -> None:
    chat_session = _open_session(
        session, student, ["hola", "sí"], ConversationStage.CONFIRM_RESULTS
    )

    response = _next(client, student, chat_session)

    assert response.json() == {"detail": RESULTS_CONFIRMED_DETAIL}
    assert chat_session.conversation_stage == ConversationStage.RESULTS
    assert _bot_messages(session, chat_session) == [BOT_QUESTION, BOT_QUESTION]


def test_confirmation_declined_keeps_collecting(
    client: TestClient, session: Session, student: User
) -> None:
    chat_session = _open_session(
        session, student, [*SIGNAL_MESSAGES, "no"], ConversationStage.CONFIRM_RESULTS
    )

    body = _next(client, student, chat_session).json()

    assert set(body) == {"bot_message"}
    assert chat_session.conversation_stage == ConversationStage.COLLECTING


def test_acceptance_with_enough_signals_moves_to_results(
    client: TestClient, session: Session, student: User
) -> None:
    chat_session = _open_session(session, student, [*SIGNAL_MESSAGES, "quiero ver mis resultados"])

    assert _next(client, student, chat_session).json() == {"detail": RESULTS_CONFIRMED_DETAIL}
    assert chat_session.conversation_stage == ConversationStage.RESULTS


def test_early_acceptance_keeps_collecting(
    client: TestClient, session: Session, student: User
) -> None:
    chat_session = _open_session(
        session, student, ["me gusta programar", "sí"], ConversationStage.QUESTIONS
    )

    body = _next(client, student, chat_session).json()

    assert set(body) == {"bot_message"}
    assert chat_session.conversation_stage == ConversationStage.COLLECTING


def test_seventh_message_asks_for_confirmation(
    client: TestClient, session: Session, student: User
) -> None:
    chat_session = _open_session(session, student, SIGNAL_MESSAGES)

    body = _next(client, student, chat_session).json()

    assert body["awaiting_confirmation"] is True
    assert body["bot_message"]["content"].startswith("¡Usuario, con lo que me contaste sobre")
    assert chat_session.conversation_stage == ConversationStage.CONFIRM_RESULTS


def test_results_stage_only_follows_up(client: TestClient, session: Session, student: User) -> None:
    chat_session = _open_session(session, student, SIGNAL_MESSAGES, ConversationStage.RESULTS)

    body = _next(client, student, chat_session).json()

    assert set(body) == {"bot_message"}
    assert chat_session.conversation_stage == ConversationStage.RESULTS


def test_regular_turn_follows_up_without_changing_stage(
    client: TestClient, session: Session, student: User
) -> None:
    chat_session = _open_session(session, student, SIGNAL_MESSAGES[:2])

    body = _next(client, student, chat_session).json()

    assert body["bot_message"]["content"] in FALLBACK_QUESTIONS[FollowupPhase.DEEPENING]
    assert chat_session.conversation_stage == ConversationStage.COLLECTING


@pytest.mark.parametrize(
    ("user_texts", "expected_name"), [([], "Usuario de Prueba"), (["hola"], None)]
)
def test_student_name_is_only_sent_on_first_followup(
    client: TestClient,
    session: Session,
    student: User,
    monkeypatch: pytest.MonkeyPatch,
    user_texts: list[str],
    expected_name: str | None,
) -> None:
    calls: list[tuple[Any, ...]] = []

    def fake_followup(*args: Any) -> str:
        calls.append(args)
        return BOT_QUESTION

    monkeypatch.setattr(open_flow, "generate_open_followup", fake_followup)
    chat_session = _open_session(session, student, user_texts)

    _next(client, student, chat_session)

    texts, history, name = calls[0]
    assert texts == user_texts
    assert [turn.role for turn in history] == [MessageType.BOT, MessageType.USER] * len(user_texts)
    assert name == expected_name


def test_guided_session_is_not_found(client: TestClient, session: Session, student: User) -> None:
    chat_session = _open_session(session, student, [], mode=ChatMode.GUIDED)

    response = _next(client, student, chat_session)

    assert response.status_code == 404
    assert response.json() == {"detail": "Sesión de chat abierto no encontrada"}


def test_other_student_session_is_not_found(
    client: TestClient, session: Session, student: User, create_user: UserFactory
) -> None:
    chat_session = _open_session(session, student, [])
    other = create_user(email="otro@kairos.dev")

    assert _next(client, other, chat_session).status_code == 404


def test_evaluator_is_forbidden(
    client: TestClient, session: Session, student: User, create_user: UserFactory
) -> None:
    chat_session = _open_session(session, student, [])
    evaluator = create_user(email="evaluador@kairos.dev", role=UserRole.EVALUATOR)

    assert _next(client, evaluator, chat_session).status_code == 403
