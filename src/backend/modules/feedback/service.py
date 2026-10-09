from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.core.exceptions import NotFoundError
from backend.modules.evaluations.service import get_student_evaluation
from backend.modules.feedback.models import EvaluatorComment, StudentFeedback
from backend.modules.feedback.schemas import FeedbackCommentUpdate, FeedbackSubmit


def _find_student_feedback(
    session: Session, evaluation_id: int, student_id: int
) -> StudentFeedback | None:
    get_student_evaluation(session, evaluation_id, student_id)
    statement = select(StudentFeedback).where(
        StudentFeedback.evaluation_id == evaluation_id,
        StudentFeedback.user_id == student_id,
    )
    return session.scalars(statement).one_or_none()


def get_student_feedback(session: Session, evaluation_id: int, student_id: int) -> StudentFeedback:
    feedback = _find_student_feedback(session, evaluation_id, student_id)
    if feedback is None:
        raise NotFoundError("Feedback no encontrado")
    return feedback


def submit_feedback(
    session: Session, evaluation_id: int, student_id: int, data: FeedbackSubmit
) -> StudentFeedback:
    feedback = _find_student_feedback(session, evaluation_id, student_id)
    if feedback is None:
        feedback = StudentFeedback(evaluation_id=evaluation_id, user_id=student_id)
        session.add(feedback)
    feedback.rating = data.rating
    feedback.dimension_ratings = data.dimension_ratings.model_dump()
    # Reenviar la calificación sin comentario no debe borrar el que ya se había guardado.
    if data.comment is not None:
        feedback.comment = data.comment
    session.commit()
    return feedback


def update_feedback_comment(
    session: Session, evaluation_id: int, student_id: int, data: FeedbackCommentUpdate
) -> StudentFeedback:
    feedback = _find_student_feedback(session, evaluation_id, student_id)
    if feedback is None:
        raise NotFoundError("Primero envía tu calificación")
    feedback.comment = data.comment
    session.commit()
    return feedback


def list_evaluation_comments(session: Session, evaluation_id: int) -> Sequence[EvaluatorComment]:
    statement = (
        select(EvaluatorComment)
        .options(joinedload(EvaluatorComment.evaluator))
        .where(EvaluatorComment.evaluation_id == evaluation_id)
        .order_by(EvaluatorComment.created_at.desc(), EvaluatorComment.comment_id.desc())
    )
    return session.scalars(statement).all()


def list_student_comments(
    session: Session, evaluation_id: int, student_id: int
) -> Sequence[EvaluatorComment]:
    get_student_evaluation(session, evaluation_id, student_id)
    return list_evaluation_comments(session, evaluation_id)
