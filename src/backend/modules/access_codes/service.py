import secrets
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from backend.core.database import paginate
from backend.core.enums import UserRole
from backend.core.exceptions import DomainError, NotFoundError
from backend.modules.access_codes.models import AccessCode
from backend.modules.access_codes.schemas import AccessCodeCreate, AccessCodeListQuery
from backend.modules.schools.scope import SchoolScope
from backend.modules.schools.service import get_school
from backend.modules.users.models import User

# Sin 0/O, 1/I/L: el estudiante copia el código a mano desde la pizarra o un mensaje.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8
INVALID_CODE = "Código de acceso inválido o vencido"


def normalize_code(raw: str) -> str:
    compact = "".join(character for character in raw.upper() if character.isalnum())
    half = CODE_LENGTH // 2
    return f"{compact[:half]}-{compact[half:]}"


def _generate_unique_code(session: Session) -> str:
    while True:
        code = normalize_code("".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH)))
        if not session.scalar(select(exists().where(AccessCode.code == code))):
            return code


def _is_assignable_evaluator(evaluator: User | None, school_id: int) -> bool:
    return (
        evaluator is not None
        and evaluator.is_active
        and evaluator.role == UserRole.EVALUATOR
        and evaluator.school_id == school_id
    )


def create_code(session: Session, scope: SchoolScope, data: AccessCodeCreate) -> AccessCode:
    school_id = get_school(session, scope.target_school(data.school_id)).school_id
    if data.evaluator_id is not None:
        evaluator = session.get(User, data.evaluator_id)
        if not _is_assignable_evaluator(evaluator, school_id):
            raise NotFoundError("Evaluador no encontrado")
    if data.expires_at is not None and data.expires_at <= datetime.now(UTC):
        raise DomainError("La fecha de vencimiento debe ser futura")

    access_code = AccessCode(
        school_id=school_id,
        code=_generate_unique_code(session),
        label=data.label,
        evaluator_id=data.evaluator_id,
        expires_at=data.expires_at,
        max_uses=data.max_uses,
    )
    session.add(access_code)
    session.commit()
    return access_code


def list_codes(
    session: Session, scope: SchoolScope, query: AccessCodeListQuery
) -> Sequence[AccessCode]:
    statement = (
        select(AccessCode)
        .where(*scope.conditions(AccessCode.school_id))
        .order_by(AccessCode.created_at.desc(), AccessCode.code_id.desc())
    )
    return session.scalars(paginate(statement, query)).all()


def revoke_code(session: Session, scope: SchoolScope, code_id: int) -> None:
    access_code = session.get(AccessCode, code_id)
    if access_code is None or not scope.covers(access_code.school_id):
        raise NotFoundError("Código no encontrado")
    if not access_code.is_active:
        raise DomainError("El código ya está revocado")
    access_code.is_active = False
    session.commit()


def _is_usable(access_code: AccessCode) -> bool:
    return (
        access_code.is_active
        and (access_code.expires_at is None or access_code.expires_at > datetime.now(UTC))
        and (access_code.max_uses is None or access_code.uses < access_code.max_uses)
    )


def redeem_code(session: Session, raw_code: str) -> AccessCode:
    # El bloqueo de la fila impide que dos registros simultáneos superen max_uses.
    statement = (
        select(AccessCode).where(AccessCode.code == normalize_code(raw_code)).with_for_update()
    )
    access_code = session.scalar(statement)
    if access_code is None or not _is_usable(access_code):
        raise DomainError(INVALID_CODE)
    access_code.uses += 1
    return access_code


def evaluator_for(access_code: AccessCode) -> User | None:
    """Evaluador al que se asigna quien usa el código, si sigue disponible en ese colegio."""
    evaluator = access_code.evaluator
    return evaluator if _is_assignable_evaluator(evaluator, access_code.school_id) else None
