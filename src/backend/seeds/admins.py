from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.enums import UserRole
from backend.core.security import hash_password
from backend.modules.users.models import User


def seed_admins(session: Session) -> int:
    admins = get_settings().seed_admins
    if not admins:
        return 0

    rows = [
        {
            "full_name": admin.full_name,
            "email": admin.email.lower(),
            "password_hash": hash_password(admin.password),
            "role": UserRole.ADMIN,
        }
        for admin in admins
    ]
    statement = insert(User).values(rows).on_conflict_do_nothing().returning(User.user_id)
    return len(session.scalars(statement).all())
