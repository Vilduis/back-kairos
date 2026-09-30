from typing import Any

from sqlalchemy import CheckConstraint, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.database import Base, CreatedAt, IntPk, cascade_fk


class StudentFeedback(Base):
    __tablename__ = "student_feedback"
    __table_args__ = (
        UniqueConstraint("evaluation_id", "user_id"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="rating_range"),
    )

    feedback_id: Mapped[IntPk]
    evaluation_id: Mapped[int] = cascade_fk("evaluations.evaluation_id", index=False)
    user_id: Mapped[int] = cascade_fk("users.user_id")
    rating: Mapped[int]
    dimension_ratings: Mapped[dict[str, Any] | None]
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[CreatedAt]


class EvaluatorComment(Base):
    __tablename__ = "evaluator_comments"

    comment_id: Mapped[IntPk]
    evaluation_id: Mapped[int] = cascade_fk("evaluations.evaluation_id")
    evaluator_id: Mapped[int] = cascade_fk("users.user_id")
    comment_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[CreatedAt]
