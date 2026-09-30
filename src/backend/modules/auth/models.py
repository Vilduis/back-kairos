from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.database import Base, CreatedAt, IntPk, cascade_fk


class PasswordReset(Base):
    __tablename__ = "password_resets"

    reset_id: Mapped[IntPk]
    user_id: Mapped[int] = cascade_fk("users.user_id")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime]
    created_at: Mapped[CreatedAt]
