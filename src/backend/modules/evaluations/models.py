from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base, CreatedAt, IntPk, cascade_fk
from backend.core.enums import CompatibleMode, EvaluationMode, EvaluationStatus, QuestionType

if TYPE_CHECKING:
    from backend.modules.chat.models import ChatSession


class Question(Base):
    __tablename__ = "questions"

    question_id: Mapped[IntPk]
    question_text: Mapped[str] = mapped_column(Text, unique=True)
    question_type: Mapped[QuestionType]
    category: Mapped[str | None] = mapped_column(Text)
    display_order: Mapped[int | None]
    options: Mapped[dict[str, Any] | None]
    validation_rules: Mapped[dict[str, Any] | None]
    compatible_modes: Mapped[CompatibleMode] = mapped_column(default=CompatibleMode.GUIDED)


class Evaluation(Base):
    __tablename__ = "evaluations"
    __table_args__ = (CheckConstraint("progress BETWEEN 0 AND 1", name="progress_range"),)

    evaluation_id: Mapped[IntPk]
    user_id: Mapped[int] = cascade_fk("users.user_id")
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.session_id", ondelete="CASCADE"), unique=True
    )
    evaluation_mode: Mapped[EvaluationMode]
    status: Mapped[EvaluationStatus] = mapped_column(default=EvaluationStatus.IN_PROGRESS)
    progress: Mapped[float] = mapped_column(default=0.0)
    started_at: Mapped[CreatedAt]
    completed_at: Mapped[datetime | None]

    session: Mapped[ChatSession] = relationship(back_populates="evaluation")
    answers: Mapped[list[UserAnswer]] = relationship(
        back_populates="evaluation", cascade="all, delete-orphan", passive_deletes=True
    )
    result: Mapped[EvaluationResult | None] = relationship(
        back_populates="evaluation", cascade="all, delete-orphan", passive_deletes=True
    )


class UserAnswer(Base):
    __tablename__ = "user_answers"
    __table_args__ = (UniqueConstraint("evaluation_id", "question_id"),)

    answer_id: Mapped[IntPk]
    evaluation_id: Mapped[int] = cascade_fk("evaluations.evaluation_id", index=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.question_id"), index=True)
    answer_text: Mapped[str | None] = mapped_column(Text)
    selected_options: Mapped[dict[str, Any] | None]
    answered_at: Mapped[CreatedAt]

    evaluation: Mapped[Evaluation] = relationship(back_populates="answers")
    question: Mapped[Question] = relationship()


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    result_id: Mapped[IntPk]
    evaluation_id: Mapped[int] = mapped_column(
        ForeignKey("evaluations.evaluation_id", ondelete="CASCADE"), unique=True
    )
    riasec_scores: Mapped[dict[str, Any]]
    top_careers: Mapped[list[dict[str, Any]]]
    metrics: Mapped[dict[str, Any]]
    generated_at: Mapped[CreatedAt]

    evaluation: Mapped[Evaluation] = relationship(back_populates="result")
