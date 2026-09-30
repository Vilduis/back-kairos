from typing import Annotated

from fastapi import APIRouter, Depends

from backend.api.deps import require_role
from backend.core.database import SessionDep
from backend.core.enums import UserRole
from backend.modules.users import service
from backend.modules.users.models import User
from backend.modules.users.schemas import ProfileUpdate, UserRead


def add_profile_routes(router: APIRouter, role: UserRole) -> None:
    role_user = Depends(require_role(role))

    @router.get("/me", response_model=UserRead)
    def read_profile(user: Annotated[User, role_user]) -> User:
        return user

    @router.put("/me", response_model=UserRead)
    def update_profile(
        data: ProfileUpdate, user: Annotated[User, role_user], session: SessionDep
    ) -> User:
        return service.update_profile(session, user, data)
