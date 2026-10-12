from datetime import date
from typing import Literal

from pydantic import BaseModel

from backend.core.enums import EvaluationMode, RiasecType, UserRole
from backend.core.schemas import OrderDirection, Pagination
from backend.modules.users.schemas import AccountCreate, ProfileUpdate

type DashboardRange = Literal["7d", "30d", "90d", "12m"]
type UserOrderField = Literal["created_at", "full_name", "email", "role", "last_login"]


class AdminUserCreate(AccountCreate):
    role: Literal[UserRole.EVALUATOR, UserRole.SCHOOL_ADMIN, UserRole.ADMIN]
    school_id: int | None = None


class AdminUserUpdate(ProfileUpdate):
    role: UserRole | None = None
    is_active: bool | None = None
    school_id: int | None = None


class UserFilter(BaseModel):
    school_id: int | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    assigned: bool | None = None
    q: str | None = None


class UserListQuery(UserFilter, Pagination):
    order_by: UserOrderField = "created_at"
    order_dir: OrderDirection = "desc"


class FeedbackFilter(BaseModel):
    student_id: int | None = None
    evaluation_id: int | None = None


class FeedbackListQuery(FeedbackFilter, Pagination):
    order_dir: OrderDirection = "desc"


class DashboardQuery(BaseModel):
    range: DashboardRange = "30d"
    school_id: int | None = None


class Kpi(BaseModel):
    current: float | None
    previous: float | None


class ActivityPoint(BaseModel):
    period: date
    students: int
    evaluations: int


class ModeBreakdown(BaseModel):
    mode: EvaluationMode
    completed: int
    in_progress: int


class EvaluatorLoad(BaseModel):
    user_id: int
    full_name: str
    students: int


class AdminDashboard(BaseModel):
    active_users: dict[UserRole, int]
    assigned_students: int
    evaluators_with_students: int
    new_students: Kpi
    completed_evaluations: Kpi
    completion_rate: Kpi
    average_rating: Kpi | None
    activity: list[ActivityPoint]
    riasec_profiles: dict[RiasecType, int]
    modes: list[ModeBreakdown]
    evaluator_load: list[EvaluatorLoad]
    feedback_dimensions: dict[str, float] | None
