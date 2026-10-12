from datetime import datetime
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from backend.core.schemas import Pagination

Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class CodeEvaluator(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    full_name: str


class AccessCodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code_id: int
    code: str
    label: str
    school_id: int
    evaluator: CodeEvaluator | None
    expires_at: datetime | None
    max_uses: int | None
    uses: int
    is_active: bool
    created_at: datetime


class AccessCodeCreate(BaseModel):
    label: Label
    school_id: int | None = None
    evaluator_id: int | None = None
    expires_at: AwareDatetime | None = None
    max_uses: int | None = Field(default=None, ge=1)


class AccessCodeListQuery(Pagination):
    school_id: int | None = None
