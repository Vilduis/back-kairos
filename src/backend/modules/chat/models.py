from datetime import datetime

from sqlalchemy import ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base, CreatedAt, IntPk, cascade_fk
from backend.core.enums import ChatMode, ConversationStage, MessageType, SessionStatus
from backend.modules.evaluations.models import Evaluation, Question


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    session_id: Mapped[IntPk]
    user_id: Mapped[int] = cascade_fk("users.user_id")
    chat_mode: Mapped[ChatMode]
    conversation_stage: Mapped[ConversationStage] = mapped_column(default=ConversationStage.WELCOME)
    current_question_id: Mapped[int | None] = mapped_column(
        ForeignKey("questions.question_id", ondelete="SET NULL")
    )
    status: Mapped[SessionStatus] = mapped_column(default=SessionStatus.ACTIVE)
    started_at: Mapped[CreatedAt]
    last_activity: Mapped[datetime] = mapped_column(server_default=func.now())

    current_question: Mapped[Question | None] = relationship()
    messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="session",
        order_by="ChatMessage.message_order",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    evaluation: Mapped[Evaluation | None] = relationship(
        back_populates="session", cascade="all, delete-orphan", passive_deletes=True
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (UniqueConstraint("session_id", "message_order"),)

    message_id: Mapped[IntPk]
    session_id: Mapped[int] = cascade_fk("chat_sessions.session_id", index=False)
    message_type: Mapped[MessageType]
    content: Mapped[str] = mapped_column(Text)
    message_order: Mapped[int]
    sent_at: Mapped[CreatedAt]

    session: Mapped[ChatSession] = relationship(back_populates="messages")
