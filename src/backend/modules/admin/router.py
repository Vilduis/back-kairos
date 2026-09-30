from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Query, status

from backend.api.deps import AdminUser
from backend.core.database import SessionDep
from backend.core.enums import UserRole
from backend.core.schemas import Message
from backend.modules.admin import service
from backend.modules.admin.schemas import (
    AdminUserCreate,
    AdminUserUpdate,
    FeedbackListQuery,
    UserListQuery,
)
from backend.modules.assignments import service as assignments_service
from backend.modules.assignments.models import EvaluatorAssignment
from backend.modules.assignments.schemas import AssignmentListQuery, AssignmentRead
from backend.modules.feedback.models import StudentFeedback
from backend.modules.feedback.schemas import StudentFeedbackRead
from backend.modules.users import service as users_service
from backend.modules.users.models import User
from backend.modules.users.router import add_profile_routes
from backend.modules.users.schemas import UserRead

router = APIRouter(prefix="/admin", tags=["admin"])
add_profile_routes(router, UserRole.ADMIN)


@router.post("/users", response_model=UserRead)
def create_user(data: AdminUserCreate, _: AdminUser, session: SessionDep) -> User:
    return users_service.create_account(session, data, data.role)


@router.get("/users", response_model=list[UserRead])
def list_users(
    query: Annotated[UserListQuery, Query()], _: AdminUser, session: SessionDep
) -> Sequence[User]:
    return service.list_users(session, query)


@router.get("/users/{user_id}", response_model=UserRead)
def read_user(user_id: int, _: AdminUser, session: SessionDep) -> User:
    return service.get_user(session, user_id)


@router.put("/users/{user_id}", response_model=UserRead)
def update_user(user_id: int, data: AdminUserUpdate, _: AdminUser, session: SessionDep) -> User:
    return service.update_user(session, user_id, data)


@router.delete("/users/{user_id}")
def deactivate_user(user_id: int, admin: AdminUser, session: SessionDep) -> Message:
    service.deactivate_user(session, user_id, admin)
    return Message(detail="Usuario desactivado correctamente. Sus datos han sido conservados.")


@router.post("/assignments", status_code=status.HTTP_201_CREATED)
def create_assignment(
    student_id: int, evaluator_id: int, _: AdminUser, session: SessionDep
) -> Message:
    assignments_service.create_assignment(session, student_id, evaluator_id)
    return Message(detail="Asignación creada exitosamente")


@router.get("/assignments", response_model=list[AssignmentRead])
def list_assignments(
    query: Annotated[AssignmentListQuery, Query()], _: AdminUser, session: SessionDep
) -> Sequence[EvaluatorAssignment]:
    return assignments_service.list_assignments(session, query)


@router.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assignment(assignment_id: int, _: AdminUser, session: SessionDep) -> None:
    assignments_service.delete_assignment(session, assignment_id)


@router.get("/feedback", response_model=list[StudentFeedbackRead])
def list_feedback(
    query: Annotated[FeedbackListQuery, Query()], _: AdminUser, session: SessionDep
) -> Sequence[StudentFeedback]:
    return service.list_feedback(session, query)
