from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.core.enums import AssignmentStatus
from backend.core.schemas import Pagination


class AssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    assignment_id: int
    evaluator_id: int
    student_id: int
    status: AssignmentStatus
    assigned_date: datetime


class AssignmentListQuery(Pagination):
    evaluator_id: int | None = None
    student_id: int | None = None
    status: AssignmentStatus | None = None
