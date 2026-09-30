from collections.abc import Sequence

from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from backend.core.database import paginate
from backend.core.enums import UserRole
from backend.core.exceptions import DomainError, NotFoundError
from backend.core.schemas import OrderDirection
from backend.modules.admin.schemas import (
    AdminUserUpdate,
    FeedbackListQuery,
    UserListQuery,
)
from backend.modules.feedback.models import StudentFeedback
from backend.modules.users.models import User
from backend.modules.users.service import apply_profile_changes

STUDENT_PROFILE_LOCKED = (
    "Solo se puede cambiar el estado de un estudiante; "
    "su información de perfil no es editable por el administrador."
)

USER_ORDER_COLUMNS: dict[str, InstrumentedAttribute] = {
    "created_at": User.created_at,
    "full_name": User.full_name,
    "email": User.email,
    "role": User.role,
    "last_login": User.last_login,
}


def _ordered(column: InstrumentedAttribute, direction: OrderDirection) -> ColumnElement:
    return column.asc() if direction == "asc" else column.desc()


def get_user(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise NotFoundError("Usuario no encontrado")
    return user


def list_users(session: Session, query: UserListQuery) -> Sequence[User]:
    statement = select(User)
    if query.role is not None:
        statement = statement.where(User.role == query.role)
    if query.is_active is not None:
        statement = statement.where(User.is_active == query.is_active)
    if query.q:
        pattern = f"%{query.q}%"
        statement = statement.where(or_(User.full_name.ilike(pattern), User.email.ilike(pattern)))
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
        or (
            data.educational_institution is not None
            and data.educational_institution != student.educational_institution
        )
        or (data.role is not None and data.role != student.role)
    )


def update_user(session: Session, user_id: int, data: AdminUserUpdate) -> User:
    user = get_user(session, user_id)
    # Los estudiantes son dueños de su perfil: el administrador solo gestiona su estado.
    if user.role == UserRole.STUDENT:
        if _changes_student_profile(user, data):
            raise DomainError(STUDENT_PROFILE_LOCKED)
    else:
        apply_profile_changes(session, user, data)
        if data.role is not None:
            user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active
    session.commit()
    return user


def deactivate_user(session: Session, user_id: int, admin: User) -> None:
    user = get_user(session, user_id)
    if user.user_id == admin.user_id:
        raise DomainError("No puedes desactivar tu propia cuenta")
    if not user.is_active:
        raise DomainError("El usuario ya se encuentra desactivado")
    user.is_active = False
    session.commit()


def list_feedback(session: Session, query: FeedbackListQuery) -> Sequence[StudentFeedback]:
    statement = select(StudentFeedback)
    if query.student_id is not None:
        statement = statement.where(StudentFeedback.user_id == query.student_id)
    if query.evaluation_id is not None:
        statement = statement.where(StudentFeedback.evaluation_id == query.evaluation_id)
    statement = statement.order_by(
        _ordered(StudentFeedback.created_at, query.order_dir),
        _ordered(StudentFeedback.feedback_id, query.order_dir),
    )
    return session.scalars(paginate(statement, query)).all()
