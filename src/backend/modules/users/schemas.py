from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from backend.core.enums import UserRole
from backend.modules.schools.schemas import SchoolSummary

FullName = Field(min_length=1, max_length=100)
Password = Field(min_length=6, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    full_name: str
    email: EmailStr
    role: UserRole
    school: SchoolSummary | None
    is_active: bool
    created_at: datetime
    last_login: datetime | None


class ConsentStatus(BaseModel):
    accepted: bool


class AccountCreate(BaseModel):
    full_name: str = FullName
    email: EmailStr
    password: str = Password


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
