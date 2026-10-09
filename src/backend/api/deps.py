from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from backend.core.database import SessionDep
from backend.core.enums import UserRole
from backend.core.exceptions import AuthenticationError, PermissionDeniedError
from backend.core.security import decode_access_token
from backend.ml.artifacts import ModelArtifacts, get_model_artifacts
from backend.modules.users.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

ROLE_DENIED_MESSAGES = {
    UserRole.STUDENT: "Acceso solo para estudiantes",
    UserRole.EVALUATOR: "Se requieren privilegios de evaluador",
    UserRole.ADMIN: "Se requieren privilegios de administrador",
}


def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)], session: SessionDep
) -> User:
    subject = decode_access_token(token) if token else None
    user = session.get(User, int(subject)) if subject and subject.isdigit() else None
    if user is None or not user.is_active:
        raise AuthenticationError("Credenciales de autenticación inválidas")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(role: UserRole) -> Callable[[User], User]:
    def dependency(user: CurrentUser) -> User:
        if user.role != role:
            raise PermissionDeniedError(ROLE_DENIED_MESSAGES[role])
        return user

    return dependency


StudentUser = Annotated[User, Depends(require_role(UserRole.STUDENT))]
EvaluatorUser = Annotated[User, Depends(require_role(UserRole.EVALUATOR))]
AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]

ModelArtifactsDep = Annotated[ModelArtifacts, Depends(get_model_artifacts)]
