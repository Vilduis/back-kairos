from typing import Literal

from backend.core.enums import UserRole
from backend.core.schemas import OrderDirection, Pagination
from backend.modules.users.schemas import AccountCreate, ProfileUpdate

type UserOrderField = Literal["created_at", "full_name", "email", "role", "last_login"]


class AdminUserCreate(AccountCreate):
    role: Literal[UserRole.EVALUATOR, UserRole.ADMIN]


class AdminUserUpdate(ProfileUpdate):
    role: UserRole | None = None
    is_active: bool | None = None


class UserListQuery(Pagination):
    role: UserRole | None = None
    is_active: bool | None = None
    q: str | None = None
    order_by: UserOrderField = "created_at"
    order_dir: OrderDirection = "desc"


class FeedbackListQuery(Pagination):
    student_id: int | None = None
    evaluation_id: int | None = None
    order_dir: OrderDirection = "desc"
