import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.enums import ChatMode, ConversationStage, SessionStatus, UserRole
from backend.modules.chat.models import ChatMessage, ChatSession
from backend.modules.evaluations.models import Evaluation, EvaluationResult, Question, UserAnswer
from backend.modules.feedback.models import EvaluatorComment, StudentFeedback
from backend.modules.users.models import User
from backend.seeds.riasec_questions import _question_rows
from tests.conftest import UserFactory, auth_headers


@pytest.fixture
def student(create_user: UserFactory) -> User:
    return create_user()


@pytest.fixture
def headers(student: User) -> dict[str, str]:
    return auth_headers(student)


@pytest.fixture
def questions(session: Session) -> list[Question]:
    questions = [Question(**row) for row in _question_rows()]
    session.add_all(questions)
    session.flush()
    return questions


def _create_session(
    client: TestClient, headers: dict[str, str], mode: ChatMode = ChatMode.GUIDED
) -> int:
    response = client.post("/chat/sessions", json={"chat_mode": mode}, headers=headers)
    assert response.status_code == 200
    return response.json()["session_id"]


def _answer(
    client: TestClient, headers: dict[str, str], session_id: int, question_id: int, value: int
) -> dict:
    response = client.post(
        f"/chat/sessions/{session_id}/answers",
        json={"question_id": question_id, "selected_options": {"selected": [value]}},
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()


def _answer_all(
    client: TestClient, headers: dict[str, str], session_id: int, questions: list[Question]
) -> None:
    for question in questions:
        value = 5 if question.category == "riasec_I" else 2
        _answer(client, headers, session_id, question.question_id, value)


def test_session_crud(client: TestClient, headers: dict[str, str], student: User) -> None:
    first = _create_session(client, headers)
    second = _create_session(client, headers, ChatMode.OPEN)

    listed = client.get("/chat/sessions", headers=headers).json()
    detail = client.get(f"/chat/sessions/{first}", headers=headers).json()
    deleted = client.delete(f"/chat/sessions/{first}", headers=headers)

    assert [item["session_id"] for item in listed] == [first, second]
    assert detail["user_id"] == student.user_id
    assert detail["conversation_stage"] == ConversationStage.WELCOME
    assert detail["status"] == SessionStatus.ACTIVE
    assert deleted.json() == {"detail": "Sesión eliminada correctamente"}
    assert client.get(f"/chat/sessions/{first}", headers=headers).status_code == 404


def test_sessions_are_isolated_between_students(
    client: TestClient, create_user: UserFactory, headers: dict[str, str]
) -> None:
    session_id = _create_session(client, headers)
    other = auth_headers(create_user(email="otro@kairos.dev"))

    assert client.get("/chat/sessions", headers=other).json() == []
    for method, path in (
        ("GET", f"/chat/sessions/{session_id}"),
        ("GET", f"/chat/sessions/{session_id}/messages"),
        ("DELETE", f"/chat/sessions/{session_id}"),
        ("POST", f"/chat/sessions/{session_id}/complete"),
        ("GET", f"/chat/sessions/{session_id}/results"),
    ):
        response = client.request(method, path, headers=other)
        assert response.status_code == 404
        assert response.json() == {"detail": "Sesión de chat no encontrada"}


def test_evaluator_is_forbidden(client: TestClient, create_user: UserFactory) -> None:
    evaluator = create_user(email="evaluador@kairos.dev", role=UserRole.EVALUATOR)

    response = client.get("/chat/sessions", headers=auth_headers(evaluator))

    assert response.status_code == 403


def test_server_assigns_message_order(client: TestClient, headers: dict[str, str]) -> None:
    session_id = _create_session(client, headers)

    for text in ("hola", "me gusta la ciencia"):
        response = client.post(
            "/chat/messages",
            json={"session_id": session_id, "content": text, "message_order": 99},
            headers=headers,
        )
        assert response.status_code == 200

    messages = client.get(f"/chat/sessions/{session_id}/messages", headers=headers).json()
    assert [(m["message_order"], m["content"]) for m in messages] == [
        (1, "hola"),
        (2, "me gusta la ciencia"),
    ]
    assert {m["message_type"] for m in messages} == {"user"}


def test_rejects_non_user_messages(client: TestClient, headers: dict[str, str]) -> None:
    session_id = _create_session(client, headers)

    response = client.post(
        "/chat/messages",
        json={"session_id": session_id, "content": "soy el bot", "message_type": "bot"},
        headers=headers,
    )

    assert response.status_code == 422


def test_first_question_does_not_write(
    client: TestClient, session: Session, headers: dict[str, str], questions: list[Question]
) -> None:
    response = client.get("/chat/guided/first-question", headers=headers)

    body = response.json()
    assert response.status_code == 200
    assert body["completed"] is False
    assert body["question"]["question_id"] == questions[0].question_id
    assert body["total"] == len(questions)
    assert body["answered"] == 0
    assert session.scalar(select(func.count()).select_from(ChatSession)) == 0


def test_first_question_without_questions(client: TestClient, headers: dict[str, str]) -> None:
    response = client.get("/chat/guided/first-question", headers=headers)

    assert response.status_code == 404
    assert response.json() == {"detail": "No hay preguntas configuradas"}


def test_next_question_is_idempotent_and_tracks_progress(
    client: TestClient, session: Session, headers: dict[str, str], questions: list[Question]
) -> None:
    session_id = _create_session(client, headers)
    path = f"/chat/sessions/{session_id}/next-question"

    first = client.get(path, headers=headers).json()
    repeated = client.get(path, headers=headers).json()
    _answer(client, headers, session_id, questions[0].question_id, 4)
    after_answer = client.get(path, headers=headers).json()

    assert first == repeated
    assert first["question"]["question_id"] == questions[0].question_id
    assert after_answer["question"]["question_id"] == questions[1].question_id
    assert after_answer["answered"] == 1
    assert session.get(ChatSession, session_id).current_question_id == questions[1].question_id


def test_next_question_completed_when_all_answered(
    client: TestClient, headers: dict[str, str], questions: list[Question]
) -> None:
    session_id = _create_session(client, headers)
    _answer_all(client, headers, session_id, questions)

    response = client.get(f"/chat/sessions/{session_id}/next-question", headers=headers)

    assert response.json() == {
        "completed": True,
        "question": None,
        "total": len(questions),
        "answered": len(questions),
    }


def test_next_question_without_questions(client: TestClient, headers: dict[str, str]) -> None:
    session_id = _create_session(client, headers)

    response = client.get(f"/chat/sessions/{session_id}/next-question", headers=headers)

    assert response.status_code == 404
    assert response.json() == {"detail": "No hay preguntas configuradas"}


def test_next_question_rejects_open_session(
    client: TestClient, headers: dict[str, str], questions: list[Question]
) -> None:
    session_id = _create_session(client, headers, ChatMode.OPEN)

    response = client.get(f"/chat/sessions/{session_id}/next-question", headers=headers)

    assert response.status_code == 404
    assert response.json() == {"detail": "Sesión de chat guiado no encontrada"}


def test_answer_upsert(
    client: TestClient, session: Session, headers: dict[str, str], questions: list[Question]
) -> None:
    session_id = _create_session(client, headers)
    question_id = questions[0].question_id

    first = _answer(client, headers, session_id, question_id, 2)
    second = _answer(client, headers, session_id, question_id, 5)

    assert first["answer_id"] == second["answer_id"]
    assert second["selected_options"] == {"selected": [5]}
    assert session.scalar(select(func.count()).select_from(UserAnswer)) == 1


def test_answer_unknown_question(client: TestClient, headers: dict[str, str]) -> None:
    session_id = _create_session(client, headers)

    response = client.post(
        f"/chat/sessions/{session_id}/answers",
        json={"question_id": 999_999, "selected_options": {"selected": [3]}},
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Pregunta no encontrada"}


def test_complete_and_results(
    client: TestClient, session: Session, headers: dict[str, str], questions: list[Question]
) -> None:
    session_id = _create_session(client, headers)
    _answer_all(client, headers, session_id, questions)

    completed = client.post(f"/chat/sessions/{session_id}/complete", headers=headers)
    repeated = client.post(f"/chat/sessions/{session_id}/complete", headers=headers)
    results = client.get(f"/chat/sessions/{session_id}/results", headers=headers)

    body = completed.json()
    assert completed.status_code == 200
    assert body["detail"] == "Evaluación completada"
    assert repeated.json() == body
    result = results.json()
    assert result["result_id"] == body["result_id"]
    assert max(result["riasec_scores"], key=result["riasec_scores"].get) == "I"
    assert len(result["top_careers"]) == 3

    chat_session = session.get(ChatSession, session_id)
    assert chat_session.status == SessionStatus.COMPLETED
    assert chat_session.conversation_stage == ConversationStage.RESULTS
    assert chat_session.evaluation.progress == 1.0
    assert chat_session.evaluation.completed_at is not None


def test_results_without_evaluation(client: TestClient, headers: dict[str, str]) -> None:
    session_id = _create_session(client, headers)

    response = client.get(f"/chat/sessions/{session_id}/results", headers=headers)

    assert response.status_code == 404
    assert response.json() == {"detail": "Evaluación no encontrada"}


def test_delete_cascades(
    client: TestClient,
    session: Session,
    create_user: UserFactory,
    student: User,
    headers: dict[str, str],
    questions: list[Question],
) -> None:
    session_id = _create_session(client, headers)
    client.post(
        "/chat/messages", json={"session_id": session_id, "content": "hola"}, headers=headers
    )
    _answer_all(client, headers, session_id, questions)
    evaluation_id = client.post(f"/chat/sessions/{session_id}/complete", headers=headers).json()[
        "evaluation_id"
    ]
    evaluator = create_user(email="evaluador@kairos.dev", role=UserRole.EVALUATOR)
    session.add_all(
        [
            StudentFeedback(evaluation_id=evaluation_id, user_id=student.user_id, rating=5),
            EvaluatorComment(
                evaluation_id=evaluation_id, evaluator_id=evaluator.user_id, comment_text="Bien"
            ),
        ]
    )
    session.flush()
    session.expunge_all()

    response = client.delete(f"/chat/sessions/{session_id}", headers=headers)

    assert response.status_code == 200
    for model in (
        ChatSession,
        ChatMessage,
        Evaluation,
        UserAnswer,
        EvaluationResult,
        StudentFeedback,
        EvaluatorComment,
    ):
        assert session.scalar(select(func.count()).select_from(model)) == 0
