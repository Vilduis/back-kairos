from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.core.enums import (
    ChatMode,
    CompatibleMode,
    ConversationStage,
    MessageType,
    QuestionType,
    SessionStatus,
)


class ChatSessionCreate(BaseModel):
    chat_mode: ChatMode
    conversation_stage: ConversationStage = ConversationStage.WELCOME


class ChatSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: int
    user_id: int
    chat_mode: ChatMode
    conversation_stage: ConversationStage
    status: SessionStatus
    started_at: datetime
    last_activity: datetime


class ChatMessageCreate(BaseModel):
    session_id: int
    content: str = Field(min_length=1)
    message_type: Literal[MessageType.USER] = MessageType.USER


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    message_id: int
    session_id: int
    message_type: MessageType
    content: str
    message_order: int
    sent_at: datetime


class QuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    question_id: int
    question_text: str
    question_type: QuestionType
    category: str | None
    display_order: int | None
    options: dict[str, Any] | None
    validation_rules: dict[str, Any] | None
    compatible_modes: CompatibleMode


class GuidedProgress(BaseModel):
    completed: bool
    question: QuestionRead | None
    total: int
    answered: int


class SelectedOptions(BaseModel):
    selected: list[int] = Field(min_length=1)


class SessionAnswerCreate(BaseModel):
    question_id: int
    answer_text: str | None = None
    selected_options: SelectedOptions | None = None


class UserAnswerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    answer_id: int
    evaluation_id: int
    question_id: int
    answer_text: str | None
    selected_options: SelectedOptions | None
    answered_at: datetime


class CompletionResponse(BaseModel):
    detail: str
    evaluation_id: int
    result_id: int


class OpenTurnResponse(BaseModel):
    bot_message: ChatMessageRead | None = None
    detail: str | None = None
    awaiting_confirmation: bool | None = None
