import pytest
from fastapi.testclient import TestClient

from backend.core.enums import UserRole
from tests.conftest import UserFactory, auth_headers

PROFILE_PATHS = [
    (UserRole.STUDENT, "/students/me"),
    (UserRole.EVALUATOR, "/evaluator/me"),
    (UserRole.ADMIN, "/admin/me"),
]


@pytest.mark.parametrize(("role", "path"), PROFILE_PATHS)
def test_reads_own_profile(
    client: TestClient, create_user: UserFactory, role: UserRole, path: str
) -> None:
    user = create_user(role=role)

    response = client.get(path, headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json()["user_id"] == user.user_id
    assert response.json()["role"] == role


@pytest.mark.parametrize(("role", "path"), PROFILE_PATHS)
def test_updates_only_sent_fields(
    client: TestClient, create_user: UserFactory, role: UserRole, path: str
) -> None:
    user = create_user(role=role)

    response = client.put(
        path,
        json={"full_name": "Nombre Nuevo", "email": "Nuevo@Kairos.dev"},
        headers=auth_headers(user),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Nombre Nuevo"
    assert body["email"] == "nuevo@kairos.dev"
    assert body["educational_institution"] == user.educational_institution


def test_rejects_email_of_another_user(client: TestClient, create_user: UserFactory) -> None:
    create_user(email="ocupado@kairos.dev")
    user = create_user()

    response = client.put(
        "/students/me", json={"email": "OCUPADO@kairos.dev"}, headers=auth_headers(user)
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Este correo ya está registrado"}


def test_keeps_own_email(client: TestClient, create_user: UserFactory) -> None:
    user = create_user()

    response = client.put(
        "/students/me", json={"email": "estudiante@kairos.dev"}, headers=auth_headers(user)
    )

    assert response.status_code == 200


def test_profile_is_scoped_by_role(client: TestClient, create_user: UserFactory) -> None:
    student = create_user()

    response = client.get("/admin/me", headers=auth_headers(student))

    assert response.status_code == 403
