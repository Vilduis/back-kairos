from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.security import OAuth2PasswordRequestForm

from backend.core.database import SessionDep
from backend.core.enums import UserRole
from backend.core.schemas import Message
from backend.integrations.email import send_password_reset_email
from backend.modules.auth import service
from backend.modules.auth.schemas import (
    PasswordResetConfirm,
    PasswordResetRequest,
    TokenResponse,
)
from backend.modules.users import service as users_service
from backend.modules.users.models import User
from backend.modules.users.schemas import AccountCreate, UserRead

router = APIRouter(tags=["authentication"])


@router.post("/token")
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep
) -> TokenResponse:
    return service.login(session, form.username, form.password)


@router.post("/signup", response_model=UserRead)
def signup(data: AccountCreate, session: SessionDep) -> User:
    return users_service.create_account(session, data, UserRole.STUDENT)


@router.post("/password-reset/request")
def request_password_reset(
    data: PasswordResetRequest, session: SessionDep, background_tasks: BackgroundTasks
) -> Message:
    token = service.create_password_reset_token(session, data.email)
    if token is not None:
        background_tasks.add_task(send_password_reset_email, data.email, token)
    return Message(detail="Si el correo existe, se ha enviado un enlace")


@router.post("/password-reset/confirm")
def confirm_password_reset(data: PasswordResetConfirm, session: SessionDep) -> Message:
    service.reset_password(session, data.token, data.new_password)
    return Message(detail="Contraseña actualizada")
