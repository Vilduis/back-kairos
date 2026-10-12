from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Query, status

from backend.api.deps import AdminUser, SchoolScopeDep, StaffUser
from backend.core.database import SessionDep
from backend.core.enums import UserRole
from backend.core.schemas import Count, Message
from backend.modules.access_codes import service as access_codes_service
from backend.modules.access_codes.models import AccessCode
from backend.modules.access_codes.schemas import (
    AccessCodeCreate,
    AccessCodeListQuery,
    AccessCodeRead,
)
from backend.modules.admin import dashboard, service
from backend.modules.admin.schemas import (
    AdminDashboard,
    AdminUserCreate,
    AdminUserUpdate,
    DashboardQuery,
    FeedbackFilter,
    FeedbackListQuery,
    UserFilter,
    UserListQuery,
)
from backend.modules.assignments import service as assignments_service
from backend.modules.assignments.models import EvaluatorAssignment
from backend.modules.assignments.schemas import AssignmentListQuery, AssignmentRead
from backend.modules.evaluations.models import Evaluation
from backend.modules.evaluations.schemas import EvaluationRead
from backend.modules.feedback.models import StudentFeedback
from backend.modules.feedback.schemas import StudentFeedbackRead
from backend.modules.schools import service as schools_service
from backend.modules.schools.models import School
from backend.modules.schools.schemas import SchoolRead, SchoolWrite
from backend.modules.users.models import User
from backend.modules.users.router import add_profile_routes
from backend.modules.users.schemas import UserRead

router = APIRouter(prefix="/admin", tags=["admin"])
add_profile_routes(router, UserRole.ADMIN, UserRole.SCHOOL_ADMIN)


@router.get("/schools", response_model=list[SchoolRead])
def list_schools(_: AdminUser, session: SessionDep) -> Sequence[School]:
    return schools_service.list_schools(session)


@router.post("/schools", response_model=SchoolRead, status_code=status.HTTP_201_CREATED)
def create_school(data: SchoolWrite, _: AdminUser, session: SessionDep) -> School:
    return schools_service.create_school(session, data)


@router.put("/schools/{school_id}", response_model=SchoolRead)
def rename_school(school_id: int, data: SchoolWrite, _: AdminUser, session: SessionDep) -> School:
    return schools_service.rename_school(session, school_id, data)


@router.get("/access-codes", response_model=list[AccessCodeRead])
def list_access_codes(
    query: Annotated[AccessCodeListQuery, Query()], scope: SchoolScopeDep, session: SessionDep
) -> Sequence[AccessCode]:
    return access_codes_service.list_codes(session, scope.narrow(query.school_id), query)


@router.post("/access-codes", response_model=AccessCodeRead, status_code=status.HTTP_201_CREATED)
def create_access_code(
    data: AccessCodeCreate, scope: SchoolScopeDep, session: SessionDep
) -> AccessCode:
    return access_codes_service.create_code(session, scope, data)


@router.delete("/access-codes/{code_id}")
def revoke_access_code(code_id: int, scope: SchoolScopeDep, session: SessionDep) -> Message:
    access_codes_service.revoke_code(session, scope, code_id)
    return Message(detail="Código revocado. Ya no permite crear cuentas.")


@router.get("/dashboard")
def read_dashboard(
    query: Annotated[DashboardQuery, Query()], scope: SchoolScopeDep, session: SessionDep
) -> AdminDashboard:
    return dashboard.get_dashboard(session, scope.narrow(query.school_id), query.range)


@router.post("/users", response_model=UserRead)
def create_user(data: AdminUserCreate, scope: SchoolScopeDep, session: SessionDep) -> User:
    return service.create_staff_user(session, scope, data)


@router.get("/users", response_model=list[UserRead])
def list_users(
    query: Annotated[UserListQuery, Query()], scope: SchoolScopeDep, session: SessionDep
) -> Sequence[User]:
    return service.list_users(session, scope.narrow(query.school_id), query)


@router.get("/users/count")
def count_users(
    query: Annotated[UserFilter, Query()], scope: SchoolScopeDep, session: SessionDep
) -> Count:
    return Count(total=service.count_users(session, scope.narrow(query.school_id), query))


@router.get("/users/{user_id}", response_model=UserRead)
def read_user(user_id: int, scope: SchoolScopeDep, session: SessionDep) -> User:
    return service.get_user(session, scope, user_id)


@router.get("/users/{user_id}/evaluations", response_model=list[EvaluationRead])
def list_user_evaluations(
    user_id: int, scope: SchoolScopeDep, session: SessionDep
) -> Sequence[Evaluation]:
    return service.list_user_evaluations(session, scope, user_id)


@router.put("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: int, data: AdminUserUpdate, scope: SchoolScopeDep, session: SessionDep
) -> User:
    return service.update_user(session, scope, user_id, data)


@router.delete("/users/{user_id}")
def deactivate_user(
    user_id: int, staff: StaffUser, scope: SchoolScopeDep, session: SessionDep
) -> Message:
    service.deactivate_user(session, scope, user_id, staff)
    return Message(detail="Usuario desactivado correctamente. Sus datos han sido conservados.")


@router.post("/assignments", status_code=status.HTTP_201_CREATED)
def create_assignment(
    student_id: int, evaluator_id: int, scope: SchoolScopeDep, session: SessionDep
) -> Message:
    assignments_service.create_assignment(session, scope, student_id, evaluator_id)
    return Message(detail="Asignación creada exitosamente")


@router.get("/assignments", response_model=list[AssignmentRead])
def list_assignments(
    query: Annotated[AssignmentListQuery, Query()], scope: SchoolScopeDep, session: SessionDep
) -> Sequence[EvaluatorAssignment]:
    return assignments_service.list_assignments(session, scope, query)


@router.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assignment(assignment_id: int, scope: SchoolScopeDep, session: SessionDep) -> None:
    assignments_service.delete_assignment(session, scope, assignment_id)


@router.get("/feedback", response_model=list[StudentFeedbackRead])
def list_feedback(
    query: Annotated[FeedbackListQuery, Query()], _: AdminUser, session: SessionDep
) -> Sequence[StudentFeedback]:
    return service.list_feedback(session, query)


@router.get("/feedback/count")
def count_feedback(
    query: Annotated[FeedbackFilter, Query()], _: AdminUser, session: SessionDep
) -> Count:
    return Count(total=service.count_feedback(session, query))
