from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base, CreatedAt, IntPk, cascade_fk
from backend.core.enums import AssignmentStatus
from backend.modules.users.models import User


class EvaluatorAssignment(Base):
    __tablename__ = "evaluator_assignments"
    __table_args__ = (UniqueConstraint("evaluator_id", "student_id"),)

    assignment_id: Mapped[IntPk]
    evaluator_id: Mapped[int] = cascade_fk("users.user_id", index=False)
    student_id: Mapped[int] = cascade_fk("users.user_id")
    status: Mapped[AssignmentStatus] = mapped_column(default=AssignmentStatus.ACTIVE)
    assigned_date: Mapped[CreatedAt]

    evaluator: Mapped[User] = relationship(foreign_keys=[evaluator_id])
    student: Mapped[User] = relationship(foreign_keys=[student_id])
