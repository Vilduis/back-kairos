from fastapi import APIRouter

from backend.api.deps import StudentUser
from backend.core.database import SessionDep
from backend.modules.chat import open_flow
from backend.modules.chat.schemas import OpenTurnResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "/sessions/{session_id}/open/next",
    response_model=OpenTurnResponse,
    response_model_exclude_none=True,
)
def next_open_turn(session_id: int, student: StudentUser, session: SessionDep) -> OpenTurnResponse:
    return open_flow.next_open_turn(session, student, session_id)
