from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base, CreatedAt, IntPk, cascade_fk
from backend.modules.users.models import User


class AccessCode(Base):
    __tablename__ = "school_access_codes"
    __table_args__ = (
        CheckConstraint("max_uses IS NULL OR max_uses > 0", name="max_uses_positive"),
        CheckConstraint("uses >= 0", name="uses_not_negative"),
    )

    code_id: Mapped[IntPk]
    school_id: Mapped[int] = cascade_fk("schools.school_id")
    code: Mapped[str] = mapped_column(String(9), unique=True)
    label: Mapped[str] = mapped_column(String(100))
    evaluator_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL")
    )
    expires_at: Mapped[datetime | None]
    max_uses: Mapped[int | None]
    uses: Mapped[int] = mapped_column(default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
    created_at: Mapped[CreatedAt]

    evaluator: Mapped[User | None] = relationship()
