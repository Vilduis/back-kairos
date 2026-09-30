from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from backend.core.enums import EvaluationMode, EvaluationStatus


class EvaluationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    evaluation_id: int
    user_id: int
    session_id: int
    evaluation_mode: EvaluationMode
    status: EvaluationStatus
    progress: float
    started_at: datetime
    completed_at: datetime | None


class EvaluationResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    result_id: int
    evaluation_id: int
    riasec_scores: dict[str, float]
    top_careers: list[dict[str, Any]]
    metrics: dict[str, float]
    generated_at: datetime
