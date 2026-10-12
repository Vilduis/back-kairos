from collections.abc import Sequence

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from backend.core.database import paginate
from backend.core.enums import AssignmentStatus, UserRole
from backend.core.exceptions import DomainError, NotFoundError, PermissionDeniedError
from backend.core.schemas import OrderDirection
from backend.modules.admin.schemas import (
    AdminUserCreate,
    AdminUserUpdate,
    FeedbackFilter,
    FeedbackListQuery,
    UserFilter,
    UserListQuery,
)
from backend.modules.assignments.models import EvaluatorAssignment
from backend.modules.assignments.service import remove_user_assignments
from backend.modules.evaluations.models import Evaluation
from backend.modules.evaluations.service import list_student_evaluations
from backend.modules.feedback.models import StudentFeedback
from backend.modules.schools.scope import SCHOOL_REQUIRED, SchoolScope
from backend.modules.schools.service import get_school
from backend.modules.users.models import User
from backend.modules.users.service import apply_profile_changes, create_account

STUDENT_PROFILE_LOCKED = (
    "Solo se puede cambiar el estado de un estudiante; "
    "su información de perfil no es editable por el administrador."
)

KAIROS_ONLY = "Solo el equipo de Kairos puede gestionar administradores"
# Un administrador de colegio gestiona a su personal de orientación, no a otros administradores.
SCHOOL_MANAGED_ROLES = (UserRole.STUDENT, UserRole.EVALUATOR)

USER_ORDER_COLUMNS: dict[str, InstrumentedAttribute] = {
    "created_at": User.created_at,
    "full_name": User.full_name,
    "email": User.email,
    "role": User.role,
    "last_login": User.last_login,
}


def _ordered(column: InstrumentedAttribute, direction: OrderDirection) -> ColumnElement:
    return column.asc() if direction == "asc" else column.desc()


def get_user(session: Session, scope: SchoolScope, user_id: int) -> User:
    user = session.get(User, user_id)
    # Un usuario de otro colegio responde igual que uno inexistente para no revelar que existe.
    if user is None or not scope.covers(user.school_id):
        raise NotFoundError("Usuario no encontrado")
    return user


def _ensure_can_manage(scope: SchoolScope, role: UserRole) -> None:
    if not scope.is_superadmin and role not in SCHOOL_MANAGED_ROLES:
        raise PermissionDeniedError(KAIROS_ONLY)


def _school_for_new_user(session: Session, scope: SchoolScope, data: AdminUserCreate) -> int | None:
    _ensure_can_manage(scope, data.role)
    if data.role == UserRole.ADMIN:
        return None
    return get_school(session, scope.target_school(data.school_id)).school_id


def create_staff_user(session: Session, scope: SchoolScope, data: AdminUserCreate) -> User:
    school_id = _school_for_new_user(session, scope, data)
    user = create_account(session, data, data.role, school_id=school_id)
    session.commit()
    return user


def _user_conditions(scope: SchoolScope, query: UserFilter) -> list[ColumnElement[bool]]:
    conditions = scope.conditions()
    if query.role is not None:
        conditions.append(User.role == query.role)
    if query.is_active is not None:
        conditions.append(User.is_active == query.is_active)
    if query.assigned is not None:
        has_assignment = (
            select(EvaluatorAssignment.assignment_id)
            .where(
                EvaluatorAssignment.status == AssignmentStatus.ACTIVE,
                or_(
                    EvaluatorAssignment.student_id == User.user_id,
                    EvaluatorAssignment.evaluator_id == User.user_id,
                ),
            )
            .exists()
        )
        conditions.append(has_assignment if query.assigned else ~has_assignment)
    if query.q:
        pattern = f"%{query.q}%"
        conditions.append(or_(User.full_name.ilike(pattern), User.email.ilike(pattern)))
    return conditions


def count_users(session: Session, scope: SchoolScope, query: UserFilter) -> int:
    statement = select(func.count()).select_from(User).where(*_user_conditions(scope, query))
    return session.scalar(statement) or 0


def list_users(session: Session, scope: SchoolScope, query: UserListQuery) -> Sequence[User]:
    statement = select(User).where(*_user_conditions(scope, query))
    # El user_id desempata filas con el mismo valor para que la paginación sea estable.
    statement = statement.order_by(
        _ordered(USER_ORDER_COLUMNS[query.order_by], query.order_dir),
        _ordered(User.user_id, query.order_dir),
    )
    return session.scalars(paginate(statement, query)).all()


def _changes_student_profile(student: User, data: AdminUserUpdate) -> bool:
    return (
        (data.full_name is not None and data.full_name != student.full_name)
        or (data.email is not None and data.email.lower() != student.email.lower())
        or (data.role is not None and data.role != student.role)
    )


def _move_to_school(session: Session, scope: SchoolScope, user: User, school_id: int) -> None:
    if not scope.is_superadmin:
        raise PermissionDeniedError(
            "Solo el equipo de Kairos puede cambiar el colegio de un usuario"
        )
    user.school_id = get_school(session, school_id).school_id


def _change_role(scope: SchoolScope, user: User, role: UserRole) -> None:
    if not scope.is_superadmin:
        raise PermissionDeniedError("Solo el equipo de Kairos puede cambiar el rol de un usuario")
    user.role = role
    # Los administradores generales no pertenecen a un colegio; el resto, siempre a uno.
    if role == UserRole.ADMIN:
        user.school_id = None
    elif user.school_id is None:
        raise DomainError(SCHOOL_REQUIRED)


def update_user(session: Session, scope: SchoolScope, user_id: int, data: AdminUserUpdate) -> User:
    user = get_user(session, scope, user_id)
    _ensure_can_manage(scope, user.role)
    previous_role, previous_school = user.role, user.school_id
    if data.school_id is not None:
        _move_to_school(session, scope, user, data.school_id)
    # Los estudiantes son dueños de su perfil: el administrador solo gestiona su estado.
    if user.role == UserRole.STUDENT:
        if _changes_student_profile(user, data):
            raise DomainError(STUDENT_PROFILE_LOCKED)
    else:
        apply_profile_changes(session, user, data)
        if data.role is not None and data.role != user.role:
            _change_role(scope, user, data.role)
    if data.is_active is not None:
        user.is_active = data.is_active
    # Una asignación solo existe entre un estudiante y un evaluador activos del mismo colegio.
    if not user.is_active or (user.role, user.school_id) != (previous_role, previous_school):
        remove_user_assignments(session, user.user_id)
    session.commit()
    return user


def deactivate_user(session: Session, scope: SchoolScope, user_id: int, admin: User) -> None:
    user = get_user(session, scope, user_id)
    _ensure_can_manage(scope, user.role)
    if user.user_id == admin.user_id:
        raise DomainError("No puedes desactivar tu propia cuenta")
    if not user.is_active:
        raise DomainError("El usuario ya se encuentra desactivado")
    user.is_active = False
    remove_user_assignments(session, user.user_id)
    session.commit()


def _feedback_conditions(query: FeedbackFilter) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if query.student_id is not None:
        conditions.append(StudentFeedback.user_id == query.student_id)
    if query.evaluation_id is not None:
        conditions.append(StudentFeedback.evaluation_id == query.evaluation_id)
    return conditions


def count_feedback(session: Session, query: FeedbackFilter) -> int:
    statement = select(func.count()).select_from(StudentFeedback)
    return session.scalar(statement.where(*_feedback_conditions(query))) or 0


def list_feedback(session: Session, query: FeedbackListQuery) -> Sequence[StudentFeedback]:
    statement = select(StudentFeedback).where(*_feedback_conditions(query))
    statement = statement.order_by(
        _ordered(StudentFeedback.created_at, query.order_dir),
        _ordered(StudentFeedback.feedback_id, query.order_dir),
    )
    return session.scalars(paginate(statement, query)).all()


def list_user_evaluations(
    session: Session, scope: SchoolScope, user_id: int
) -> Sequence[Evaluation]:
    user = get_user(session, scope, user_id)
    if user.role != UserRole.STUDENT:
        raise DomainError("Solo los estudiantes tienen evaluaciones")
    return list_student_evaluations(session, user_id)
