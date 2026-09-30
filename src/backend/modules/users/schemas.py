from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from backend.core.enums import UserRole

FullName = Field(min_length=1, max_length=100)
Password = Field(min_length=6, max_length=128)
Institution = Field(default=None, max_length=150)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    full_name: str
    email: EmailStr
    educational_institution: str | None
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login: datetime | None


class AccountCreate(BaseModel):
    full_name: str = FullName
    email: EmailStr
    password: str = Password
    educational_institution: str | None = Institution


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    educational_institution: str | None = Institution
