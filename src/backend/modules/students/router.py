from collections.abc import Sequence

from fastapi import APIRouter

from backend.api.deps import StudentUser
from backend.core.database import SessionDep
from backend.core.enums import UserRole
from backend.modules.feedback import service as feedback_service
from backend.modules.feedback.models import EvaluatorComment, StudentFeedback
from backend.modules.feedback.schemas import (
    FeedbackCommentUpdate,
    FeedbackSubmit,
    ReceivedCommentRead,
    StudentFeedbackRead,
)
from backend.modules.users.router import add_profile_routes

router = APIRouter(prefix="/students", tags=["students"])
add_profile_routes(router, UserRole.STUDENT)


@router.post("/evaluations/{evaluation_id}/feedback", response_model=StudentFeedbackRead)
def submit_feedback(
    evaluation_id: int, data: FeedbackSubmit, student: StudentUser, session: SessionDep
) -> StudentFeedback:
    return feedback_service.submit_feedback(session, evaluation_id, student.user_id, data)


@router.patch("/evaluations/{evaluation_id}/feedback", response_model=StudentFeedbackRead)
def update_feedback_comment(
    evaluation_id: int, data: FeedbackCommentUpdate, student: StudentUser, session: SessionDep
) -> StudentFeedback:
    return feedback_service.update_feedback_comment(session, evaluation_id, student.user_id, data)


@router.get("/evaluations/{evaluation_id}/feedback", response_model=StudentFeedbackRead)
def read_feedback(evaluation_id: int, student: StudentUser, session: SessionDep) -> StudentFeedback:
    return feedback_service.get_student_feedback(session, evaluation_id, student.user_id)


@router.get("/evaluations/{evaluation_id}/comments", response_model=list[ReceivedCommentRead])
def list_evaluator_comments(
    evaluation_id: int, student: StudentUser, session: SessionDep
) -> Sequence[EvaluatorComment]:
    return feedback_service.list_student_comments(session, evaluation_id, student.user_id)
