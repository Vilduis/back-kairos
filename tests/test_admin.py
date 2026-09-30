import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy.orm import Session

from backend.core.enums import AssignmentStatus, UserRole
from backend.modules.assignments.models import EvaluatorAssignment
from backend.modules.feedback.models import StudentFeedback
from backend.modules.users.models import User
from tests.conftest import EvaluationFactory, UserFactory, auth_headers

NEW_USER = {
    "full_name": "Eva Luna",
    "email": "Eva.Luna@Kairos.dev",
    "password": "clave-segura",
    "role": "evaluator",
}

DIMENSIONS = {
    "ease_of_use": 4,
    "clarity": 5,
    "usefulness": 4,
    "interaction": 3,
    "satisfaction": 5,
}


@pytest.fixture
def admin(create_user: UserFactory) -> User:
    return create_user(email="admin@kairos.dev", role=UserRole.ADMIN)


@pytest.fixture
def headers(admin: User) -> dict[str, str]:
    return auth_headers(admin)


def ids(response: Response) -> list[int]:
    return [item["user_id"] for item in response.json()]


class TestCreateUser:
    @pytest.mark.parametrize("role", ["evaluator", "admin"])
    def test_creates_staff_user(self, client: TestClient, headers: dict, role: str) -> None:
        response = client.post("/admin/users", json={**NEW_USER, "role": role}, headers=headers)

        assert response.status_code == 200
        assert response.json()["email"] == "eva.luna@kairos.dev"
        assert response.json()["role"] == role

    def test_rejects_student_role(self, client: TestClient, headers: dict) -> None:
        response = client.post(
            "/admin/users", json={**NEW_USER, "role": "student"}, headers=headers
        )

        assert response.status_code == 422

    def test_rejects_active_email(
        self, client: TestClient, headers: dict, create_user: UserFactory
    ) -> None:
        create_user(email="eva.luna@kairos.dev")

        response = client.post("/admin/users", json=NEW_USER, headers=headers)

        assert response.status_code == 400
        assert response.json() == {"detail": "Email ya registrado"}

    def test_reactivates_deactivated_account(
        self, client: TestClient, headers: dict, create_user: UserFactory
    ) -> None:
        user = create_user(email="eva.luna@kairos.dev", is_active=False)

        response = client.post("/admin/users", json=NEW_USER, headers=headers)

        assert response.status_code == 200
        assert response.json()["user_id"] == user.user_id
        assert user.is_active
        assert user.role == UserRole.EVALUATOR


class TestListUsers:
    @pytest.fixture
    def users(self, create_user: UserFactory, admin: User) -> dict[str, User]:
        ana = create_user(email="ana@kairos.dev")
        ana.full_name = "Ana Pérez"
        bruno = create_user(email="bruno@kairos.dev", role=UserRole.EVALUATOR)
        bruno.full_name = "Bruno Díaz"
        carla = create_user(email="carla@colegio.edu", is_active=False)
        carla.full_name = "Carla Ruiz"
        return {"admin": admin, "ana": ana, "bruno": bruno, "carla": carla}

    def test_filters_by_role_and_state(
        self, client: TestClient, headers: dict, users: dict[str, User]
    ) -> None:
        response = client.get(
            "/admin/users", params={"role": "student", "is_active": True}, headers=headers
        )

        assert ids(response) == [users["ana"].user_id]

    def test_searches_name_or_email(
        self, client: TestClient, headers: dict, users: dict[str, User]
    ) -> None:
        by_name = client.get("/admin/users", params={"q": "díaz"}, headers=headers)
        by_email = client.get("/admin/users", params={"q": "COLEGIO"}, headers=headers)

        assert ids(by_name) == [users["bruno"].user_id]
        assert ids(by_email) == [users["carla"].user_id]

    def test_orders_and_paginates(
        self, client: TestClient, headers: dict, users: dict[str, User]
    ) -> None:
        params = {"order_by": "email", "order_dir": "asc", "skip": 1, "limit": 2}

        response = client.get("/admin/users", params=params, headers=headers)

        assert ids(response) == [users["ana"].user_id, users["bruno"].user_id]

    def test_defaults_to_newest_first(
        self, client: TestClient, headers: dict, users: dict[str, User]
    ) -> None:
        response = client.get("/admin/users", headers=headers)

        assert ids(response) == [
            user.user_id for user in sorted(users.values(), key=lambda u: -u.user_id)
        ]

    @pytest.mark.parametrize(
        "params", [{"order_by": "password_hash"}, {"order_dir": "up"}, {"limit": 501}]
    )
    def test_rejects_invalid_params(self, client: TestClient, headers: dict, params: dict) -> None:
        response = client.get("/admin/users", params=params, headers=headers)

        assert response.status_code == 422


class TestReadUser:
    def test_reads_user(self, client: TestClient, headers: dict, admin: User) -> None:
        response = client.get(f"/admin/users/{admin.user_id}", headers=headers)

        assert response.status_code == 200
        assert response.json()["email"] == admin.email

    def test_returns_404_for_missing_user(self, client: TestClient, headers: dict) -> None:
        response = client.get("/admin/users/999999", headers=headers)

        assert response.status_code == 404
        assert response.json() == {"detail": "Usuario no encontrado"}


class TestUpdateUser:
    def test_updates_staff_profile_role_and_state(
        self, client: TestClient, headers: dict, create_user: UserFactory
    ) -> None:
        evaluator = create_user(email="eval@kairos.dev", role=UserRole.EVALUATOR)
        payload = {
            "full_name": "Nuevo Nombre",
            "email": "Nuevo@Kairos.dev",
            "role": "admin",
            "is_active": False,
        }

        response = client.put(f"/admin/users/{evaluator.user_id}", json=payload, headers=headers)

        assert response.status_code == 200
        body = response.json()
        assert body["full_name"] == "Nuevo Nombre"
        assert body["email"] == "nuevo@kairos.dev"
        assert body["role"] == "admin"
        assert body["is_active"] is False

    def test_rejects_taken_email(
        self, client: TestClient, headers: dict, create_user: UserFactory
    ) -> None:
        evaluator = create_user(email="eval@kairos.dev", role=UserRole.EVALUATOR)

        response = client.put(
            f"/admin/users/{evaluator.user_id}", json={"email": "admin@kairos.dev"}, headers=headers
        )

        assert response.status_code == 400
        assert response.json() == {"detail": "Email ya registrado"}

    def test_changes_student_state_with_unchanged_profile(
        self, client: TestClient, headers: dict, create_user: UserFactory
    ) -> None:
        student = create_user()
        payload = {
            "full_name": student.full_name,
            "email": student.email.upper(),
            "role": "student",
            "is_active": False,
        }

        response = client.put(f"/admin/users/{student.user_id}", json=payload, headers=headers)

        assert response.status_code == 200
        assert response.json()["is_active"] is False

    @pytest.mark.parametrize(
        "change",
        [
            {"full_name": "Otro"},
            {"email": "otro@kairos.dev"},
            {"educational_institution": "Otro Colegio"},
            {"role": "evaluator"},
        ],
    )
    def test_rejects_student_profile_changes(
        self, client: TestClient, headers: dict, create_user: UserFactory, change: dict
    ) -> None:
        student = create_user()

        response = client.put(f"/admin/users/{student.user_id}", json=change, headers=headers)

        assert response.status_code == 400
        assert response.json() == {
            "detail": "Solo se puede cambiar el estado de un estudiante; "
            "su información de perfil no es editable por el administrador."
        }

    def test_returns_404_for_missing_user(self, client: TestClient, headers: dict) -> None:
        response = client.put("/admin/users/999999", json={"is_active": True}, headers=headers)

        assert response.status_code == 404


class TestDeactivateUser:
    def test_deactivates_user(
        self, client: TestClient, headers: dict, create_user: UserFactory
    ) -> None:
        student = create_user()

        response = client.delete(f"/admin/users/{student.user_id}", headers=headers)

        assert response.status_code == 200
        assert response.json() == {
            "detail": "Usuario desactivado correctamente. Sus datos han sido conservados."
        }
        assert not student.is_active

    def test_rejects_own_account(self, client: TestClient, headers: dict, admin: User) -> None:
        response = client.delete(f"/admin/users/{admin.user_id}", headers=headers)

        assert response.status_code == 400
        assert response.json() == {"detail": "No puedes desactivar tu propia cuenta"}

    def test_rejects_already_deactivated(
        self, client: TestClient, headers: dict, create_user: UserFactory
    ) -> None:
        student = create_user(is_active=False)

        response = client.delete(f"/admin/users/{student.user_id}", headers=headers)

        assert response.status_code == 400
        assert response.json() == {"detail": "El usuario ya se encuentra desactivado"}

    def test_returns_404_for_missing_user(self, client: TestClient, headers: dict) -> None:
        response = client.delete("/admin/users/999999", headers=headers)

        assert response.status_code == 404


class TestAssignments:
    @pytest.fixture
    def student(self, create_user: UserFactory) -> User:
        return create_user()

    @pytest.fixture
    def evaluator(self, create_user: UserFactory) -> User:
        return create_user(email="eval@kairos.dev", role=UserRole.EVALUATOR)

    def assign(self, client: TestClient, headers: dict, student_id: int, evaluator_id: int):
        params = {"student_id": student_id, "evaluator_id": evaluator_id}
        return client.post("/admin/assignments", params=params, headers=headers)

    def test_creates_assignment(
        self, client: TestClient, headers: dict, student: User, evaluator: User
    ) -> None:
        response = self.assign(client, headers, student.user_id, evaluator.user_id)

        assert response.status_code == 201
        assert response.json() == {"detail": "Asignación creada exitosamente"}

    def test_rejects_duplicate(
        self, client: TestClient, headers: dict, student: User, evaluator: User
    ) -> None:
        self.assign(client, headers, student.user_id, evaluator.user_id)

        response = self.assign(client, headers, student.user_id, evaluator.user_id)

        assert response.status_code == 400
        assert response.json() == {"detail": "Esta asignación ya existe"}

    def test_validates_roles(
        self, client: TestClient, headers: dict, student: User, evaluator: User
    ) -> None:
        not_student = self.assign(client, headers, evaluator.user_id, evaluator.user_id)
        not_evaluator = self.assign(client, headers, student.user_id, student.user_id)

        assert not_student.status_code == 404
        assert not_student.json() == {"detail": "Estudiante no encontrado"}
        assert not_evaluator.status_code == 404
        assert not_evaluator.json() == {"detail": "Evaluador no encontrado"}

    def test_lists_with_filters(
        self,
        client: TestClient,
        headers: dict,
        session: Session,
        student: User,
        evaluator: User,
        create_user: UserFactory,
    ) -> None:
        other_student = create_user(email="otro@kairos.dev")
        active = EvaluatorAssignment(evaluator_id=evaluator.user_id, student_id=student.user_id)
        inactive = EvaluatorAssignment(
            evaluator_id=evaluator.user_id,
            student_id=other_student.user_id,
            status=AssignmentStatus.INACTIVE,
        )
        session.add_all([active, inactive])
        session.flush()

        by_status = client.get(
            "/admin/assignments",
            params={"evaluator_id": evaluator.user_id, "status": "active"},
            headers=headers,
        )
        by_student = client.get(
            "/admin/assignments", params={"student_id": other_student.user_id}, headers=headers
        )

        assert [a["assignment_id"] for a in by_status.json()] == [active.assignment_id]
        assert [a["assignment_id"] for a in by_student.json()] == [inactive.assignment_id]

    def test_rejects_invalid_status(self, client: TestClient, headers: dict) -> None:
        response = client.get("/admin/assignments", params={"status": "paused"}, headers=headers)

        assert response.status_code == 422

    def test_deletes_assignment(
        self,
        client: TestClient,
        headers: dict,
        session: Session,
        student: User,
        evaluator: User,
    ) -> None:
        assignment = EvaluatorAssignment(evaluator_id=evaluator.user_id, student_id=student.user_id)
        session.add(assignment)
        session.flush()

        response = client.delete(f"/admin/assignments/{assignment.assignment_id}", headers=headers)

        assert response.status_code == 204
        assert session.get(EvaluatorAssignment, assignment.assignment_id) is None

    def test_delete_returns_404_for_missing(self, client: TestClient, headers: dict) -> None:
        response = client.delete("/admin/assignments/999999", headers=headers)

        assert response.status_code == 404
        assert response.json() == {"detail": "Asignación no encontrada"}


class TestFeedback:
    @pytest.fixture
    def feedback(
        self,
        session: Session,
        create_user: UserFactory,
        create_evaluation: EvaluationFactory,
    ) -> list[StudentFeedback]:
        first_student = create_user()
        second_student = create_user(email="otro@kairos.dev")
        items = [
            StudentFeedback(
                evaluation_id=create_evaluation(student).evaluation_id,
                user_id=student.user_id,
                rating=rating,
                dimension_ratings=DIMENSIONS,
            )
            for student, rating in [(first_student, 5), (first_student, 3), (second_student, 4)]
        ]
        session.add_all(items)
        session.flush()
        return items

    def test_lists_newest_first(
        self, client: TestClient, headers: dict, feedback: list[StudentFeedback]
    ) -> None:
        response = client.get("/admin/feedback", headers=headers)

        assert response.status_code == 200
        assert [f["feedback_id"] for f in response.json()] == [
            f.feedback_id for f in reversed(feedback)
        ]
        assert response.json()[0]["dimension_ratings"] == DIMENSIONS

    def test_filters_and_orders_ascending(
        self, client: TestClient, headers: dict, feedback: list[StudentFeedback]
    ) -> None:
        by_student = client.get(
            "/admin/feedback",
            params={"student_id": feedback[0].user_id, "order_dir": "asc"},
            headers=headers,
        )
        by_evaluation = client.get(
            "/admin/feedback", params={"evaluation_id": feedback[2].evaluation_id}, headers=headers
        )

        assert [f["feedback_id"] for f in by_student.json()] == [
            feedback[0].feedback_id,
            feedback[1].feedback_id,
        ]
        assert [f["feedback_id"] for f in by_evaluation.json()] == [feedback[2].feedback_id]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/admin/users"),
        ("POST", "/admin/users"),
        ("GET", "/admin/users/1"),
        ("PUT", "/admin/users/1"),
        ("DELETE", "/admin/users/1"),
        ("POST", "/admin/assignments"),
        ("GET", "/admin/assignments"),
        ("DELETE", "/admin/assignments/1"),
        ("GET", "/admin/feedback"),
    ],
)
def test_requires_admin_role(
    client: TestClient, create_user: UserFactory, method: str, path: str
) -> None:
    evaluator = create_user(role=UserRole.EVALUATOR)

    response = client.request(method, path, headers=auth_headers(evaluator))

    assert response.status_code == 403
