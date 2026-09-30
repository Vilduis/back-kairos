from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.enums import UserRole
from backend.modules.auth.models import PasswordReset
from tests.conftest import DEFAULT_PASSWORD, UserFactory

SIGNUP_PAYLOAD = {
    "full_name": "Ana Torres",
    "email": "Ana.Torres@Kairos.dev",
    "password": "clave-segura",
    "educational_institution": "Colegio Kairos",
}


def login(client: TestClient, email: str, password: str = DEFAULT_PASSWORD):
    return client.post("/token", data={"username": email, "password": password})


class TestSignup:
    def test_creates_student_with_normalized_email(self, client: TestClient) -> None:
        response = client.post("/signup", json=SIGNUP_PAYLOAD)

        assert response.status_code == 200
        body = response.json()
        assert body["email"] == "ana.torres@kairos.dev"
        assert body["role"] == UserRole.STUDENT
        assert "password_hash" not in body

    def test_rejects_active_email_ignoring_case(
        self, client: TestClient, create_user: UserFactory
    ) -> None:
        create_user(email="ana.torres@kairos.dev")

        response = client.post("/signup", json=SIGNUP_PAYLOAD)

        assert response.status_code == 400
        assert response.json() == {"detail": "Email ya registrado"}

    def test_reactivates_deactivated_account(
        self, client: TestClient, create_user: UserFactory
    ) -> None:
        user = create_user(email="ana.torres@kairos.dev", role=UserRole.EVALUATOR, is_active=False)

        response = client.post("/signup", json=SIGNUP_PAYLOAD)

        assert response.status_code == 200
        assert response.json()["user_id"] == user.user_id
        assert user.is_active
        assert user.role == UserRole.STUDENT

    def test_rejects_short_password(self, client: TestClient) -> None:
        response = client.post("/signup", json={**SIGNUP_PAYLOAD, "password": "123"})

        assert response.status_code == 422


class TestLogin:
    def test_returns_token_and_user(self, client: TestClient, create_user: UserFactory) -> None:
        user = create_user()

        response = login(client, "ESTUDIANTE@kairos.dev")

        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]
        assert body["user"] == {
            "user_id": user.user_id,
            "full_name": user.full_name,
            "email": user.email,
            "role": UserRole.STUDENT,
        }
        assert user.last_login is not None

    @pytest.mark.parametrize(
        ("email", "password"),
        [("estudiante@kairos.dev", "incorrecta"), ("nadie@kairos.dev", DEFAULT_PASSWORD)],
    )
    def test_rejects_invalid_credentials(
        self, client: TestClient, create_user: UserFactory, email: str, password: str
    ) -> None:
        create_user()

        response = login(client, email, password)

        assert response.status_code == 401
        assert response.json() == {"detail": "Credenciales incorrectas"}
        assert response.headers["WWW-Authenticate"] == "Bearer"

    def test_rejects_inactive_user(self, client: TestClient, create_user: UserFactory) -> None:
        create_user(is_active=False)

        response = login(client, "estudiante@kairos.dev")

        assert response.status_code == 403
        assert response.json() == {"detail": "Usuario inactivo"}


class TestPasswordReset:
    @pytest.fixture
    def sent_emails(self, monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
        sent: list[tuple[str, str]] = []
        monkeypatch.setattr(
            "backend.modules.auth.router.send_password_reset_email",
            lambda email, token: sent.append((email, token)),
        )
        return sent

    def test_full_flow_changes_password_once(
        self, client: TestClient, create_user: UserFactory, sent_emails: list[tuple[str, str]]
    ) -> None:
        create_user()

        client.post("/password-reset/request", json={"email": "estudiante@kairos.dev"})
        [(_, token)] = sent_emails
        confirm = {"token": token, "new_password": "nueva-clave"}

        assert client.post("/password-reset/confirm", json=confirm).status_code == 200
        assert login(client, "estudiante@kairos.dev", "nueva-clave").status_code == 200
        reused = client.post("/password-reset/confirm", json=confirm)
        assert reused.status_code == 400
        assert reused.json() == {"detail": "Token inválido"}

    def test_unknown_email_gets_same_answer_without_sending(
        self, client: TestClient, sent_emails: list[tuple[str, str]]
    ) -> None:
        response = client.post("/password-reset/request", json={"email": "nadie@kairos.dev"})

        assert response.status_code == 200
        assert response.json() == {"detail": "Si el correo existe, se ha enviado un enlace"}
        assert sent_emails == []

    def test_stores_only_token_hash(
        self,
        client: TestClient,
        session: Session,
        create_user: UserFactory,
        sent_emails: list[tuple[str, str]],
    ) -> None:
        create_user()

        client.post("/password-reset/request", json={"email": "estudiante@kairos.dev"})
        [(_, token)] = sent_emails

        stored = session.scalars(select(PasswordReset.token_hash)).one()
        assert stored != token
        assert len(stored) == 64

    def test_rejects_expired_token(
        self,
        client: TestClient,
        session: Session,
        create_user: UserFactory,
        sent_emails: list[tuple[str, str]],
    ) -> None:
        create_user()
        client.post("/password-reset/request", json={"email": "estudiante@kairos.dev"})
        [(_, token)] = sent_emails
        reset = session.scalars(select(PasswordReset)).one()
        reset.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        session.flush()

        response = client.post(
            "/password-reset/confirm", json={"token": token, "new_password": "nueva-clave"}
        )

        assert response.status_code == 400
        assert response.json() == {"detail": "Token expirado"}
