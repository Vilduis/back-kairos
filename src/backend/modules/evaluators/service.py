from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.enums import UserRole
from backend.modules.assignments.models import EvaluatorAssignment
from backend.modules.assignments.service import ensure_student_assigned
from backend.modules.evaluations.models import Evaluation, EvaluationResult
from backend.modules.evaluations.service import get_evaluation, get_result, list_student_evaluations
from backend.modules.feedback.models import EvaluatorComment
from backend.modules.feedback.schemas import EvaluatorCommentCreate
from backend.modules.feedback.service import list_evaluation_comments
from backend.modules.users.models import User


def list_assigned_students(session: Session, evaluator: User) -> Sequence[User]:
    statement = (
        select(User)
        .join(EvaluatorAssignment, EvaluatorAssignment.student_id == User.user_id)
        .where(
            EvaluatorAssignment.evaluator_id == evaluator.user_id,
            User.role == UserRole.STUDENT,
        )
        .order_by(User.full_name)
    )
    return session.scalars(statement).all()


def list_assigned_student_evaluations(
    session: Session, evaluator: User, student_id: int
) -> Sequence[Evaluation]:
    ensure_student_assigned(session, evaluator.user_id, student_id)
    return list_student_evaluations(session, student_id)


def get_accessible_evaluation(session: Session, evaluator: User, evaluation_id: int) -> Evaluation:
    evaluation = get_evaluation(session, evaluation_id)
    ensure_student_assigned(session, evaluator.user_id, evaluation.user_id)
    return evaluation


def get_evaluation_result(
    session: Session, evaluator: User, evaluation_id: int
) -> EvaluationResult:
    return get_result(get_accessible_evaluation(session, evaluator, evaluation_id))


def add_comment(
    session: Session, evaluator: User, evaluation_id: int, data: EvaluatorCommentCreate
) -> EvaluatorComment:
    evaluation = get_accessible_evaluation(session, evaluator, evaluation_id)
    comment = EvaluatorComment(
        evaluation_id=evaluation.evaluation_id,
        evaluator_id=evaluator.user_id,
        comment_text=data.comment_text,
    )
    session.add(comment)
    session.commit()
    return comment


def list_comments(
    session: Session, evaluator: User, evaluation_id: int
) -> Sequence[EvaluatorComment]:
    evaluation = get_accessible_evaluation(session, evaluator, evaluation_id)
    return list_evaluation_comments(session, evaluation.evaluation_id)
