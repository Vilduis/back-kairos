from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base, CreatedAt, IntPk
from backend.core.enums import UserRole
from backend.modules.schools.models import School


class User(Base):
    __tablename__ = "users"
    # Solo el superadmin de Kairos no pertenece a un colegio.
    __table_args__ = (
        CheckConstraint("(role = 'admin') = (school_id IS NULL)", name="school_matches_role"),
    )

    user_id: Mapped[IntPk]
    full_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(default=UserRole.STUDENT)
    school_id: Mapped[int | None] = mapped_column(
        ForeignKey("schools.school_id", ondelete="RESTRICT"), index=True
    )
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
    created_at: Mapped[CreatedAt]
    last_login: Mapped[datetime | None]
    consent_accepted_at: Mapped[datetime | None]
    consent_version: Mapped[int | None]

    school: Mapped[School | None] = relationship()


Index("uq_users_email_lower", func.lower(User.email), unique=True)
