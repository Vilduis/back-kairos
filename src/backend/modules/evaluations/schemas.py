from datetime import datetime
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, model_validator

from backend.core.enums import EvaluationMode, EvaluationStatus
from backend.ml.artifacts import get_model_artifacts
from backend.ml.recommender import explain_saved_careers


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

    @model_validator(mode="after")
    def explain_with_current_catalog(self) -> Self:
        # Los resultados guardan la explicación con la que se generaron; se recalcula al leer
        # para que los resultados anteriores también muestren la explicación vigente.
        self.top_careers = explain_saved_careers(
            self.riasec_scores, self.top_careers, get_model_artifacts()
        )
        return self
