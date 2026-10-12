from collections.abc import Sequence

from fastapi import APIRouter, status

from backend.api.deps import EvaluatorUser
from backend.core.database import SessionDep
from backend.core.enums import UserRole
from backend.modules.evaluations.models import EvaluationResult
from backend.modules.evaluations.schemas import EvaluationResultRead
from backend.modules.evaluators import service
from backend.modules.evaluators.schemas import AssignedStudentSummary, EvaluatorEvaluationRead
from backend.modules.feedback.models import EvaluatorComment
from backend.modules.feedback.schemas import EvaluatorCommentCreate, EvaluatorCommentRead
from backend.modules.users.router import add_profile_routes

router = APIRouter(prefix="/evaluator", tags=["evaluator"])
add_profile_routes(router, UserRole.EVALUATOR)


@router.get("/overview")
def summarize_assigned_students(
    evaluator: EvaluatorUser, session: SessionDep
) -> list[AssignedStudentSummary]:
    return service.summarize_assigned_students(session, evaluator)


@router.get("/students/{student_id}/evaluations")
def list_student_evaluations(
    student_id: int, evaluator: EvaluatorUser, session: SessionDep
) -> list[EvaluatorEvaluationRead]:
    return service.list_assigned_student_evaluations(session, evaluator, student_id)


@router.get("/evaluations/{evaluation_id}/results", response_model=EvaluationResultRead)
def read_evaluation_result(
    evaluation_id: int, evaluator: EvaluatorUser, session: SessionDep
) -> EvaluationResult:
    return service.get_evaluation_result(session, evaluator, evaluation_id)


@router.post("/evaluations/{evaluation_id}/comments", response_model=EvaluatorCommentRead)
def add_comment(
    evaluation_id: int, data: EvaluatorCommentCreate, evaluator: EvaluatorUser, session: SessionDep
) -> EvaluatorComment:
    return service.add_comment(session, evaluator, evaluation_id, data)


@router.get("/evaluations/{evaluation_id}/comments", response_model=list[EvaluatorCommentRead])
def list_comments(
    evaluation_id: int, evaluator: EvaluatorUser, session: SessionDep
) -> Sequence[EvaluatorComment]:
    return service.list_comments(session, evaluator, evaluation_id)


@router.put(
    "/evaluations/{evaluation_id}/comments/{comment_id}", response_model=EvaluatorCommentRead
)
def update_comment(
    evaluation_id: int,
    comment_id: int,
    data: EvaluatorCommentCreate,
    evaluator: EvaluatorUser,
    session: SessionDep,
) -> EvaluatorComment:
    return service.update_comment(session, evaluator, evaluation_id, comment_id, data)


@router.delete(
    "/evaluations/{evaluation_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_comment(
    evaluation_id: int, comment_id: int, evaluator: EvaluatorUser, session: SessionDep
) -> None:
    service.delete_comment(session, evaluator, evaluation_id, comment_id)
