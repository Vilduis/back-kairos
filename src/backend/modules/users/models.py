from datetime import datetime

from sqlalchemy import Index, String, func, true
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.database import Base, CreatedAt, IntPk
from backend.core.enums import UserRole


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[IntPk]
    full_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    educational_institution: Mapped[str | None] = mapped_column(String(150))
    role: Mapped[UserRole] = mapped_column(default=UserRole.STUDENT)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
    created_at: Mapped[CreatedAt]
    last_login: Mapped[datetime | None]


Index("uq_users_email_lower", func.lower(User.email), unique=True)
