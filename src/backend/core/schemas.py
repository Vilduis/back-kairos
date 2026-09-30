from typing import Literal

from pydantic import BaseModel, Field

type OrderDirection = Literal["asc", "desc"]


class Message(BaseModel):
    detail: str


class Pagination(BaseModel):
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=500)
