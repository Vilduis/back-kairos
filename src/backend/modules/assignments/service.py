from collections.abc import Sequence

from sqlalchemy import delete, exists, or_, select
from sqlalchemy.orm import Session

from backend.core.database import paginate
from backend.core.enums import AssignmentStatus, UserRole
from backend.core.exceptions import DomainError, NotFoundError, PermissionDeniedError
from backend.modules.assignments.models import EvaluatorAssignment
from backend.modules.assignments.schemas import AssignmentListQuery
from backend.modules.schools.scope import SchoolScope
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


def _get_user_with_role(
    session: Session, scope: SchoolScope, user_id: int, role: UserRole, missing: str
) -> User:
    user = session.get(User, user_id)
    if user is None or user.role != role or not user.is_active or not scope.covers(user.school_id):
        raise NotFoundError(missing)
    return user


def _has_evaluator(session: Session, student_id: int) -> bool:
    statement = select(
        exists().where(
            EvaluatorAssignment.student_id == student_id,
            EvaluatorAssignment.status == AssignmentStatus.ACTIVE,
        )
    )
    return bool(session.scalar(statement))


def create_assignment(
    session: Session, scope: SchoolScope, student_id: int, evaluator_id: int
) -> EvaluatorAssignment:
    student = _get_user_with_role(
        session, scope, student_id, UserRole.STUDENT, "Estudiante no encontrado"
    )
    evaluator = _get_user_with_role(
        session, scope, evaluator_id, UserRole.EVALUATOR, "Evaluador no encontrado"
    )
    if student.school_id != evaluator.school_id:
        raise DomainError("El estudiante y el evaluador deben ser del mismo colegio")
    if assignment_exists(session, evaluator_id, student_id):
        raise DomainError("Esta asignación ya existe")
    if _has_evaluator(session, student_id):
        raise DomainError("Este estudiante ya tiene un evaluador asignado")
    assignment = EvaluatorAssignment(evaluator_id=evaluator_id, student_id=student_id)
    session.add(assignment)
    session.commit()
    return assignment


def list_assignments(
    session: Session, scope: SchoolScope, query: AssignmentListQuery
) -> Sequence[EvaluatorAssignment]:
    statement = (
        select(EvaluatorAssignment).join(EvaluatorAssignment.student).where(*scope.conditions())
    )
    if query.evaluator_id is not None:
        statement = statement.where(EvaluatorAssignment.evaluator_id == query.evaluator_id)
    if query.student_id is not None:
        statement = statement.where(EvaluatorAssignment.student_id == query.student_id)
    if query.status is not None:
        statement = statement.where(EvaluatorAssignment.status == query.status)
    statement = statement.order_by(EvaluatorAssignment.assignment_id)
    return session.scalars(paginate(statement, query)).all()


def delete_assignment(session: Session, scope: SchoolScope, assignment_id: int) -> None:
    assignment = session.get(EvaluatorAssignment, assignment_id)
    if assignment is None or not scope.covers(assignment.student.school_id):
        raise NotFoundError("Asignación no encontrada")
    session.delete(assignment)
    session.commit()


def remove_user_assignments(session: Session, user_id: int) -> None:
    session.execute(
        delete(EvaluatorAssignment).where(
            or_(
                EvaluatorAssignment.student_id == user_id,
                EvaluatorAssignment.evaluator_id == user_id,
            )
        )
    )
