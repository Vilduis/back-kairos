from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.enums import UserRole
from backend.core.exceptions import DomainError
from backend.core.security import hash_password
from backend.modules.users.models import User
from backend.modules.users.schemas import AccountCreate, ProfileUpdate

EMAIL_TAKEN = "Email ya registrado"


def find_user_by_email(session: Session, email: str) -> User | None:
    statement = select(User).where(func.lower(User.email) == email.lower())
    return session.scalars(statement).one_or_none()


def create_account(session: Session, data: AccountCreate, role: UserRole) -> User:
    user = find_user_by_email(session, data.email)
    if user is not None and user.is_active:
        raise DomainError(EMAIL_TAKEN)

    # Un email de una cuenta dada de baja (borrado lógico) se reutiliza reactivándola.
    if user is None:
        user = User(email=data.email.lower())
        session.add(user)
    user.full_name = data.full_name
    user.password_hash = hash_password(data.password)
    user.educational_institution = data.educational_institution
    user.role = role
    user.is_active = True
    session.commit()
    return user


def apply_profile_changes(session: Session, user: User, data: ProfileUpdate) -> None:
    if data.email is not None:
        owner = find_user_by_email(session, data.email)
        if owner is not None and owner.user_id != user.user_id:
            raise DomainError(EMAIL_TAKEN)
        user.email = data.email.lower()
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.educational_institution is not None:
        user.educational_institution = data.educational_institution


def update_profile(session: Session, user: User, data: ProfileUpdate) -> User:
    apply_profile_changes(session, user, data)
    session.commit()
    return user
