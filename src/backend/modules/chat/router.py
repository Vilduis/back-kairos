from collections.abc import Sequence

from fastapi import APIRouter

from backend.api.deps import ModelArtifactsDep, StudentUser
from backend.core.database import SessionDep
from backend.core.schemas import Message
from backend.modules.chat import sessions
from backend.modules.chat.models import ChatMessage, ChatSession
from backend.modules.chat.schemas import (
    ChatMessageCreate,
    ChatMessageRead,
    ChatSessionCreate,
    ChatSessionRead,
    CompletionResponse,
    GuidedProgress,
    SessionAnswerCreate,
    UserAnswerRead,
)
from backend.modules.chat.service import get_student_session
from backend.modules.evaluations.models import EvaluationResult, UserAnswer
from backend.modules.evaluations.schemas import EvaluationResultRead

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/sessions", response_model=ChatSessionRead)
def create_session(
    data: ChatSessionCreate, student: StudentUser, session: SessionDep
) -> ChatSession:
    return sessions.create_session(session, student.user_id, data)


@router.get("/sessions", response_model=list[ChatSessionRead])
def list_sessions(student: StudentUser, session: SessionDep) -> Sequence[ChatSession]:
    return sessions.list_sessions(session, student.user_id)


@router.get("/sessions/{session_id}", response_model=ChatSessionRead)
def read_session(session_id: int, student: StudentUser, session: SessionDep) -> ChatSession:
    return get_student_session(session, session_id, student.user_id)


@router.delete("/sessions/{session_id}", response_model=Message)
def delete_session(session_id: int, student: StudentUser, session: SessionDep) -> Message:
    sessions.delete_session(session, session_id, student.user_id)
    return Message(detail="Sesión eliminada correctamente")


@router.post("/messages", response_model=ChatMessageRead)
def add_message(data: ChatMessageCreate, student: StudentUser, session: SessionDep) -> ChatMessage:
    return sessions.add_student_message(session, student.user_id, data)


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageRead])
def list_messages(
    session_id: int, student: StudentUser, session: SessionDep
) -> Sequence[ChatMessage]:
    return sessions.list_student_messages(session, session_id, student.user_id)


@router.get("/guided/first-question", response_model=GuidedProgress)
def first_guided_question(_: StudentUser, session: SessionDep) -> GuidedProgress:
    return sessions.first_guided_question(session)


@router.get("/sessions/{session_id}/next-question", response_model=GuidedProgress)
def next_guided_question(
    session_id: int, student: StudentUser, session: SessionDep
) -> GuidedProgress:
    return sessions.next_guided_question(session, session_id, student.user_id)


@router.post("/sessions/{session_id}/answers", response_model=UserAnswerRead)
def save_answer(
    session_id: int, data: SessionAnswerCreate, student: StudentUser, session: SessionDep
) -> UserAnswer:
    return sessions.save_answer(session, session_id, student.user_id, data)


@router.post("/sessions/{session_id}/complete", response_model=CompletionResponse)
def complete_session(
    session_id: int, student: StudentUser, session: SessionDep, artifacts: ModelArtifactsDep
) -> CompletionResponse:
    return sessions.complete_session(session, session_id, student.user_id, artifacts)


@router.get("/sessions/{session_id}/results", response_model=EvaluationResultRead)
def read_session_result(
    session_id: int, student: StudentUser, session: SessionDep
) -> EvaluationResult:
    return sessions.get_session_result(session, session_id, student.user_id)
