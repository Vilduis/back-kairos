from collections.abc import Sequence

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from backend.core.database import paginate
from backend.core.enums import UserRole
from backend.core.exceptions import DomainError, NotFoundError, PermissionDeniedError
from backend.modules.assignments.models import EvaluatorAssignment
from backend.modules.assignments.schemas import AssignmentListQuery
from backend.modules.users.models import User


def assignment_exists(session: Session, evaluator_id: int, student_id: int) -> bool:
    statement = select(
        exists().where(
            EvaluatorAssignment.evaluator_id == evaluator_id,
            EvaluatorAssignment.student_id == student_id,
        )
    )
    return bool(session.scalar(statement))


def ensure_student_assigned(session: Session, evaluator_id: int, student_id: int) -> None:
    if not assignment_exists(session, evaluator_id, student_id):
        raise PermissionDeniedError("Este estudiante no está asignado a ti")


def _get_user_with_role(session: Session, user_id: int, role: UserRole, missing: str) -> User:
    user = session.get(User, user_id)
    if user is None or user.role != role:
        raise NotFoundError(missing)
    return user


def create_assignment(session: Session, student_id: int, evaluator_id: int) -> EvaluatorAssignment:
    _get_user_with_role(session, student_id, UserRole.STUDENT, "Estudiante no encontrado")
    _get_user_with_role(session, evaluator_id, UserRole.EVALUATOR, "Evaluador no encontrado")
    if assignment_exists(session, evaluator_id, student_id):
        raise DomainError("Esta asignación ya existe")
    assignment = EvaluatorAssignment(evaluator_id=evaluator_id, student_id=student_id)
    session.add(assignment)
    session.commit()
    return assignment


def list_assignments(session: Session, query: AssignmentListQuery) -> Sequence[EvaluatorAssignment]:
    statement = select(EvaluatorAssignment)
    if query.evaluator_id is not None:
        statement = statement.where(EvaluatorAssignment.evaluator_id == query.evaluator_id)
    if query.student_id is not None:
        statement = statement.where(EvaluatorAssignment.student_id == query.student_id)
    if query.status is not None:
        statement = statement.where(EvaluatorAssignment.status == query.status)
    statement = statement.order_by(EvaluatorAssignment.assignment_id)
    return session.scalars(paginate(statement, query)).all()


def delete_assignment(session: Session, assignment_id: int) -> None:
    assignment = session.get(EvaluatorAssignment, assignment_id)
    if assignment is None:
        raise NotFoundError("Asignación no encontrada")
    session.delete(assignment)
    session.commit()
