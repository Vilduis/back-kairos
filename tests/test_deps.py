import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.api.deps import AdminUser, EvaluatorUser, StudentUser
from backend.core.database import get_session
from backend.core.enums import UserRole
from backend.core.exceptions import register_exception_handlers
from tests.conftest import UserFactory, auth_headers

protected_app = FastAPI()
register_exception_handlers(protected_app)


@protected_app.get("/student")
def student_only(user: StudentUser) -> int:
    return user.user_id


@protected_app.get("/evaluator")
def evaluator_only(user: EvaluatorUser) -> int:
    return user.user_id


@protected_app.get("/admin")
def admin_only(user: AdminUser) -> int:
    return user.user_id


@pytest.fixture
def protected_client(session: Session) -> TestClient:
    protected_app.dependency_overrides[get_session] = lambda: session
    return TestClient(protected_app)


ROLE_ROUTES = [
    (UserRole.STUDENT, "/student", "Acceso solo para estudiantes"),
    (UserRole.EVALUATOR, "/evaluator", "Se requieren privilegios de evaluador"),
    (UserRole.ADMIN, "/admin", "Se requieren privilegios de administrador"),
]


@pytest.mark.parametrize(("role", "path", "_"), ROLE_ROUTES)
def test_allows_matching_role(
    protected_client: TestClient, create_user: UserFactory, role: UserRole, path: str, _: str
) -> None:
    user = create_user(role=role)

    response = protected_client.get(path, headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json() == user.user_id


@pytest.mark.parametrize(("role", "path", "message"), ROLE_ROUTES)
def test_rejects_other_roles(
    protected_client: TestClient, create_user: UserFactory, role: UserRole, path: str, message: str
) -> None:
    for other_role in set(UserRole) - {role}:
        user = create_user(email=f"{other_role}@kairos.dev", role=other_role)

        response = protected_client.get(path, headers=auth_headers(user))

        assert response.status_code == 403
        assert response.json() == {"detail": message}


@pytest.mark.parametrize(
    "headers", [{}, {"Authorization": "Bearer token-invalido"}], ids=["sin-token", "invalido"]
)
def test_rejects_missing_or_invalid_token(
    protected_client: TestClient, headers: dict[str, str]
) -> None:
    response = protected_client.get("/student", headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "Credenciales de autenticación inválidas"}


def test_rejects_deactivated_user(protected_client: TestClient, create_user: UserFactory) -> None:
    user = create_user(is_active=False)

    response = protected_client.get("/student", headers=auth_headers(user))

    assert response.status_code == 401
    assert response.json() == {"detail": "Credenciales de autenticación inválidas"}
