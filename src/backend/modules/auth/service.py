from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.enums import UserRole
from backend.core.exceptions import AuthenticationError, DomainError, PermissionDeniedError
from backend.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    generate_url_token,
    hash_password,
    hash_url_token,
    verify_password,
)
from backend.modules.access_codes.service import evaluator_for, redeem_code
from backend.modules.assignments.models import EvaluatorAssignment
from backend.modules.auth.models import PasswordReset
from backend.modules.auth.schemas import StudentSignup, TokenResponse, TokenUser
from backend.modules.users.models import User
from backend.modules.users.service import create_account, find_user_by_email


def login(session: Session, email: str, password: str) -> TokenResponse:
    user = find_user_by_email(session, email)
    password_matches = verify_password(
        password, user.password_hash if user else DUMMY_PASSWORD_HASH
    )
    if user is None or not password_matches:
        raise AuthenticationError("Credenciales incorrectas")
    if not user.is_active:
        raise PermissionDeniedError("Usuario inactivo")

    user.last_login = datetime.now(UTC)
    session.commit()
    return TokenResponse(
        access_token=create_access_token(str(user.user_id)),
        user=TokenUser.model_validate(user),
    )


def signup(session: Session, data: StudentSignup) -> User:
    access_code = redeem_code(session, data.access_code)
    student = create_account(session, data, UserRole.STUDENT, school_id=access_code.school_id)
    evaluator = evaluator_for(access_code)
    if evaluator is not None:
        session.add(EvaluatorAssignment(evaluator_id=evaluator.user_id, student_id=student.user_id))
    session.commit()
    return student


def create_password_reset_token(session: Session, email: str) -> str | None:
    user = find_user_by_email(session, email)
    if user is None or not user.is_active:
        return None

    token = generate_url_token()
    expires_in = timedelta(minutes=get_settings().password_reset_expire_minutes)
    session.execute(delete(PasswordReset).where(PasswordReset.user_id == user.user_id))
    session.add(
        PasswordReset(
            user_id=user.user_id,
            token_hash=hash_url_token(token),
            expires_at=datetime.now(UTC) + expires_in,
        )
    )
    session.commit()
    return token


def reset_password(session: Session, token: str, new_password: str) -> None:
    statement = select(PasswordReset).where(PasswordReset.token_hash == hash_url_token(token))
    reset = session.scalars(statement).one_or_none()
    if reset is None:
        raise DomainError("Token inválido")

    session.delete(reset)
    if reset.expires_at < datetime.now(UTC):
        session.commit()
        raise DomainError("Token expirado")

    session.get_one(User, reset.user_id).password_hash = hash_password(new_password)
    session.commit()
