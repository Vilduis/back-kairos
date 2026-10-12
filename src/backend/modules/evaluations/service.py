from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from backend.core.enums import RiasecType
from backend.core.exceptions import NotFoundError
from backend.modules.evaluations.models import Evaluation, EvaluationResult

EVALUATION_NOT_FOUND = "Evaluación no encontrada"


def dominant_dimension(scores: dict[str, float]) -> RiasecType:
    return RiasecType(max(scores, key=scores.__getitem__))


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


def student_evaluations[T: tuple](statement: Select[T], student_id: int) -> Select[T]:
    return statement.where(Evaluation.user_id == student_id).order_by(Evaluation.started_at.desc())


def list_student_evaluations(session: Session, student_id: int) -> Sequence[Evaluation]:
    return session.scalars(student_evaluations(select(Evaluation), student_id)).all()


def get_result(evaluation: Evaluation) -> EvaluationResult:
    if evaluation.result is None:
        raise NotFoundError("Resultados no encontrados")
    return evaluation.result
