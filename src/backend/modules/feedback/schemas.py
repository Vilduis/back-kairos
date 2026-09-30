from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

Rating = Field(ge=1, le=5)


class FeedbackDimensions(BaseModel):
    ease_of_use: int = Rating
    clarity: int = Rating
    usefulness: int = Rating
    interaction: int = Rating
    satisfaction: int = Rating


class FeedbackSubmit(BaseModel):
    rating: int = Rating
    dimension_ratings: FeedbackDimensions
    comment: str | None = None


class FeedbackCommentUpdate(BaseModel):
    comment: str | None = None


class StudentFeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    feedback_id: int
    evaluation_id: int
    user_id: int
    rating: int
    dimension_ratings: FeedbackDimensions | None
    comment: str | None
    created_at: datetime


class EvaluatorCommentCreate(BaseModel):
    comment_text: str = Field(min_length=1)


class EvaluatorCommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    comment_id: int
    evaluation_id: int
    evaluator_id: int
    comment_text: str
    created_at: datetime
