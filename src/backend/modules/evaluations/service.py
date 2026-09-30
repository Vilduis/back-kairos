from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.exceptions import NotFoundError
from backend.modules.evaluations.models import Evaluation, EvaluationResult

EVALUATION_NOT_FOUND = "Evaluación no encontrada"


def get_evaluation(session: Session, evaluation_id: int) -> Evaluation:
    evaluation = session.get(Evaluation, evaluation_id)
    if evaluation is None:
        raise NotFoundError(EVALUATION_NOT_FOUND)
    return evaluation


def get_student_evaluation(session: Session, evaluation_id: int, student_id: int) -> Evaluation:
    evaluation = session.get(Evaluation, evaluation_id)
    if evaluation is None or evaluation.user_id != student_id:
        raise NotFoundError(EVALUATION_NOT_FOUND)
    return evaluation


def list_student_evaluations(session: Session, student_id: int) -> Sequence[Evaluation]:
    statement = (
        select(Evaluation)
        .where(Evaluation.user_id == student_id)
        .order_by(Evaluation.started_at.desc())
    )
    return session.scalars(statement).all()


def get_result(evaluation: Evaluation) -> EvaluationResult:
    if evaluation.result is None:
        raise NotFoundError("Resultados no encontrados")
    return evaluation.result
