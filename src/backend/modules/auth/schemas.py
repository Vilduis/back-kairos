from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr

from backend.core.enums import UserRole
from backend.modules.users.schemas import Password


class TokenUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    full_name: str
    email: EmailStr
    role: UserRole


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: TokenUser


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Password
