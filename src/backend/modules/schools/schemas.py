from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

SchoolName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]


class SchoolSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    school_id: int
    name: str


class SchoolRead(SchoolSummary):
    created_at: datetime


class SchoolWrite(BaseModel):
    name: SchoolName
