from collections.abc import Sequence

from sqlalchemy import Exists, Select, exists, func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from backend.core.enums import EvaluationStatus, UserRole
from backend.core.exceptions import NotFoundError
from backend.modules.assignments.models import EvaluatorAssignment
from backend.modules.assignments.service import ensure_student_assigned
from backend.modules.evaluations.models import Evaluation, EvaluationResult
from backend.modules.evaluations.schemas import EvaluationRead
from backend.modules.evaluations.service import (
    dominant_dimension,
    get_evaluation,
    get_result,
    student_evaluations,
)
from backend.modules.evaluators.schemas import AssignedStudentSummary, EvaluatorEvaluationRead
from backend.modules.feedback.models import EvaluatorComment
from backend.modules.feedback.schemas import EvaluatorCommentCreate
from backend.modules.feedback.service import list_evaluation_comments
from backend.modules.users.models import User
from backend.modules.users.schemas import UserRead


def _assigned_students[T: tuple](statement: Select[T], evaluator: User) -> Select[T]:
    return (
        statement.join(EvaluatorAssignment, EvaluatorAssignment.student_id == User.user_id)
        .where(
            EvaluatorAssignment.evaluator_id == evaluator.user_id,
            User.role == UserRole.STUDENT,
        )
        .order_by(User.full_name)
    )


def _reviewed_by(evaluator: User) -> Exists:
    return exists().where(
        EvaluatorComment.evaluation_id == Evaluation.evaluation_id,
        EvaluatorComment.evaluator_id == evaluator.user_id,
    )


def summarize_assigned_students(session: Session, evaluator: User) -> list[AssignedStudentSummary]:
    completed = Evaluation.status == EvaluationStatus.COMPLETED
    reviewed = _reviewed_by(evaluator)
    stats = (
        select(
            Evaluation.user_id,
            func.count().filter(completed).label("completed"),
            func.count()
            .filter(Evaluation.status == EvaluationStatus.IN_PROGRESS)
            .label("in_progress"),
            func.count().filter(completed, ~reviewed).label("pending_review"),
            func.max(Evaluation.completed_at).label("last_completed_at"),
        )
        .group_by(Evaluation.user_id)
        .subquery()
    )
    # El perfil vigente del estudiante es el de su evaluación completada más reciente.
    latest = (
        select(Evaluation.user_id, EvaluationResult.riasec_scores)
        .join(EvaluationResult, EvaluationResult.evaluation_id == Evaluation.evaluation_id)
        .where(completed)
        .order_by(
            Evaluation.user_id,
            Evaluation.completed_at.desc().nulls_last(),
            Evaluation.evaluation_id.desc(),
        )
        .ext(distinct_on(Evaluation.user_id))
        .subquery()
    )
    statement = _assigned_students(
        select(
            User,
            func.coalesce(stats.c.completed, 0),
            func.coalesce(stats.c.in_progress, 0),
            func.coalesce(stats.c.pending_review, 0),
            stats.c.last_completed_at,
            latest.c.riasec_scores,
        )
        .outerjoin(stats, stats.c.user_id == User.user_id)
        .outerjoin(latest, latest.c.user_id == User.user_id),
        evaluator,
    )
    rows = session.execute(statement)
    return [
        AssignedStudentSummary.model_validate(
            {
                **UserRead.model_validate(user).model_dump(),
                "completed_evaluations": completed_count,
                "in_progress_evaluations": in_progress_count,
                "pending_review": pending_count,
                "last_completed_at": last_completed_at,
                "dominant_dimension": dominant_dimension(scores) if scores else None,
            }
        )
        for user, completed_count, in_progress_count, pending_count, last_completed_at, scores in (
            rows
        )
    ]


def list_assigned_student_evaluations(
    session: Session, evaluator: User, student_id: int
) -> list[EvaluatorEvaluationRead]:
    ensure_student_assigned(session, evaluator.user_id, student_id)
    rows = session.execute(
        student_evaluations(select(Evaluation, _reviewed_by(evaluator)), student_id)
    )
    return [
        EvaluatorEvaluationRead.model_validate(
            {**EvaluationRead.model_validate(evaluation).model_dump(), "reviewed": reviewed}
        )
        for evaluation, reviewed in rows
    ]


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


def _get_own_comment(
    session: Session, evaluator: User, evaluation_id: int, comment_id: int
) -> EvaluatorComment:
    evaluation = get_accessible_evaluation(session, evaluator, evaluation_id)
    comment = session.get(EvaluatorComment, comment_id)
    if (
        comment is None
        or comment.evaluation_id != evaluation.evaluation_id
        or comment.evaluator_id != evaluator.user_id
    ):
        raise NotFoundError("Observación no encontrada")
    return comment


def update_comment(
    session: Session,
    evaluator: User,
    evaluation_id: int,
    comment_id: int,
    data: EvaluatorCommentCreate,
) -> EvaluatorComment:
    comment = _get_own_comment(session, evaluator, evaluation_id, comment_id)
    comment.comment_text = data.comment_text
    session.commit()
    return comment


def delete_comment(session: Session, evaluator: User, evaluation_id: int, comment_id: int) -> None:
    session.delete(_get_own_comment(session, evaluator, evaluation_id, comment_id))
    session.commit()
