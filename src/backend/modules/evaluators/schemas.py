from datetime import datetime

from backend.core.enums import RiasecType
from backend.modules.evaluations.schemas import EvaluationRead
from backend.modules.users.schemas import UserRead


class AssignedStudentSummary(UserRead):
    completed_evaluations: int
    in_progress_evaluations: int
    pending_review: int
    last_completed_at: datetime | None
    dominant_dimension: RiasecType | None


class EvaluatorEvaluationRead(EvaluationRead):
    reviewed: bool
