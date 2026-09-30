from collections.abc import Sequence

from fastapi import APIRouter

from backend.api.deps import EvaluatorUser
from backend.core.database import SessionDep
from backend.core.enums import UserRole
from backend.modules.evaluations.models import Evaluation, EvaluationResult
from backend.modules.evaluations.schemas import EvaluationRead, EvaluationResultRead
from backend.modules.evaluators import service
from backend.modules.feedback.models import EvaluatorComment
from backend.modules.feedback.schemas import EvaluatorCommentCreate, EvaluatorCommentRead
from backend.modules.users.models import User
from backend.modules.users.router import add_profile_routes
from backend.modules.users.schemas import UserRead

router = APIRouter(prefix="/evaluator", tags=["evaluator"])
add_profile_routes(router, UserRole.EVALUATOR)


@router.get("/assignments", response_model=list[UserRead])
def list_assigned_students(evaluator: EvaluatorUser, session: SessionDep) -> Sequence[User]:
    return service.list_assigned_students(session, evaluator)


@router.get("/students/{student_id}/evaluations", response_model=list[EvaluationRead])
def list_student_evaluations(
    student_id: int, evaluator: EvaluatorUser, session: SessionDep
) -> Sequence[Evaluation]:
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
