from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from backend.core.database import SessionDep
from backend.core.enums import UserRole
from backend.core.exceptions import AuthenticationError, PermissionDeniedError
from backend.core.security import decode_access_token
from backend.ml.artifacts import ModelArtifacts, get_model_artifacts
from backend.modules.schools.scope import SchoolScope
from backend.modules.users.consent import has_current_consent
from backend.modules.users.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

ROLE_DENIED_MESSAGES = {
    UserRole.STUDENT: "Acceso solo para estudiantes",
    UserRole.EVALUATOR: "Se requieren privilegios de evaluador",
    UserRole.SCHOOL_ADMIN: "Se requieren privilegios de administrador del colegio",
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


def require_role(*roles: UserRole) -> Callable[[User], User]:
    def dependency(user: CurrentUser) -> User:
        if user.role not in roles:
            raise PermissionDeniedError(ROLE_DENIED_MESSAGES[roles[0]])
        return user

    return dependency


StudentUser = Annotated[User, Depends(require_role(UserRole.STUDENT))]
EvaluatorUser = Annotated[User, Depends(require_role(UserRole.EVALUATOR))]
AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]
StaffUser = Annotated[User, Depends(require_role(UserRole.ADMIN, UserRole.SCHOOL_ADMIN))]


def require_consent(student: StudentUser) -> None:
    if not has_current_consent(student):
        raise PermissionDeniedError("Debes aceptar el consentimiento antes de continuar")


def get_school_scope(staff: StaffUser) -> SchoolScope:
    if staff.role == UserRole.ADMIN:
        return SchoolScope(school_id=None, is_superadmin=True)
    # Sin colegio, el alcance abarcaría todos: se niega en vez de exponer otros colegios.
    if staff.school_id is None:
        raise PermissionDeniedError("Tu cuenta no está vinculada a un colegio")
    return SchoolScope(school_id=staff.school_id, is_superadmin=False)


SchoolScopeDep = Annotated[SchoolScope, Depends(get_school_scope)]

ModelArtifactsDep = Annotated[ModelArtifacts, Depends(get_model_artifacts)]
