from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.core.enums import UserRole
from backend.modules.assignments.models import EvaluatorAssignment
from backend.modules.feedback.models import EvaluatorComment
from backend.modules.users.models import User
from tests.conftest import EvaluationFactory, UserFactory, auth_headers


@pytest.fixture
def evaluator(create_user: UserFactory) -> User:
    return create_user(email="evaluador@kairos.dev", role=UserRole.EVALUATOR)


@pytest.fixture
def student(session: Session, create_user: UserFactory, evaluator: User) -> User:
    student = create_user(email="asignado@kairos.dev")
    session.add(EvaluatorAssignment(evaluator_id=evaluator.user_id, student_id=student.user_id))
    session.flush()
    return student


@pytest.fixture
def other_student(create_user: UserFactory) -> User:
    return create_user(email="ajeno@kairos.dev")


def test_lists_only_own_assigned_students(
    client: TestClient,
    session: Session,
    create_user: UserFactory,
    evaluator: User,
    student: User,
    other_student: User,
) -> None:
    other_evaluator = create_user(email="otro@kairos.dev", role=UserRole.EVALUATOR)
    session.add(
        EvaluatorAssignment(evaluator_id=other_evaluator.user_id, student_id=other_student.user_id)
    )
    session.flush()

    response = client.get("/evaluator/assignments", headers=auth_headers(evaluator))

    assert response.status_code == 200
    assert [user["user_id"] for user in response.json()] == [student.user_id]


def test_lists_evaluations_of_assigned_student(
    client: TestClient, create_evaluation: EvaluationFactory, evaluator: User, student: User
) -> None:
    evaluation = create_evaluation(student)

    response = client.get(
        f"/evaluator/students/{student.user_id}/evaluations", headers=auth_headers(evaluator)
    )

    assert response.status_code == 200
    assert [item["evaluation_id"] for item in response.json()] == [evaluation.evaluation_id]


def test_rejects_evaluations_of_unassigned_student(
    client: TestClient, evaluator: User, other_student: User
) -> None:
    response = client.get(
        f"/evaluator/students/{other_student.user_id}/evaluations", headers=auth_headers(evaluator)
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Este estudiante no está asignado a ti"}


def test_reads_result_of_assigned_student(
    client: TestClient, create_evaluation: EvaluationFactory, evaluator: User, student: User
) -> None:
    evaluation = create_evaluation(student)

    response = client.get(
        f"/evaluator/evaluations/{evaluation.evaluation_id}/results",
        headers=auth_headers(evaluator),
    )

    assert response.status_code == 200
    assert response.json()["evaluation_id"] == evaluation.evaluation_id
    assert response.json()["riasec_scores"]["I"] == 0.9


def test_result_of_missing_evaluation_is_not_found(client: TestClient, evaluator: User) -> None:
    response = client.get("/evaluator/evaluations/999999/results", headers=auth_headers(evaluator))

    assert response.status_code == 404
    assert response.json() == {"detail": "Evaluación no encontrada"}


def test_result_not_generated_is_not_found(
    client: TestClient, create_evaluation: EvaluationFactory, evaluator: User, student: User
) -> None:
    evaluation = create_evaluation(student, with_result=False)

    response = client.get(
        f"/evaluator/evaluations/{evaluation.evaluation_id}/results",
        headers=auth_headers(evaluator),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Resultados no encontrados"}


def test_rejects_result_of_unassigned_student(
    client: TestClient, create_evaluation: EvaluationFactory, evaluator: User, other_student: User
) -> None:
    evaluation = create_evaluation(other_student)

    response = client.get(
        f"/evaluator/evaluations/{evaluation.evaluation_id}/results",
        headers=auth_headers(evaluator),
    )

    assert response.status_code == 403


def test_adds_comment(
    client: TestClient, create_evaluation: EvaluationFactory, evaluator: User, student: User
) -> None:
    evaluation = create_evaluation(student)

    response = client.post(
        f"/evaluator/evaluations/{evaluation.evaluation_id}/comments",
        json={"comment_text": "Buen perfil investigativo"},
        headers=auth_headers(evaluator),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["evaluation_id"] == evaluation.evaluation_id
    assert body["evaluator_id"] == evaluator.user_id
    assert body["comment_text"] == "Buen perfil investigativo"


def test_lists_comments_newest_first(
    client: TestClient,
    session: Session,
    create_evaluation: EvaluationFactory,
    evaluator: User,
    student: User,
) -> None:
    evaluation = create_evaluation(student)
    now = datetime.now(UTC)
    session.add_all(
        EvaluatorComment(
            evaluation_id=evaluation.evaluation_id,
            evaluator_id=evaluator.user_id,
            comment_text=text,
            created_at=now - timedelta(minutes=age),
        )
        for text, age in [("antiguo", 10), ("reciente", 1)]
    )
    session.flush()

    response = client.get(
        f"/evaluator/evaluations/{evaluation.evaluation_id}/comments",
        headers=auth_headers(evaluator),
    )

    assert response.status_code == 200
    assert [item["comment_text"] for item in response.json()] == ["reciente", "antiguo"]


def test_rejects_empty_comment(
    client: TestClient, create_evaluation: EvaluationFactory, evaluator: User, student: User
) -> None:
    evaluation = create_evaluation(student)

    response = client.post(
        f"/evaluator/evaluations/{evaluation.evaluation_id}/comments",
        json={"comment_text": ""},
        headers=auth_headers(evaluator),
    )

    assert response.status_code == 422


def test_rejects_comments_of_unassigned_student(
    client: TestClient, create_evaluation: EvaluationFactory, evaluator: User, other_student: User
) -> None:
    evaluation = create_evaluation(other_student)

    response = client.get(
        f"/evaluator/evaluations/{evaluation.evaluation_id}/comments",
        headers=auth_headers(evaluator),
    )

    assert response.status_code == 403


def test_rejects_student_role(client: TestClient, student: User) -> None:
    response = client.get("/evaluator/assignments", headers=auth_headers(student))

    assert response.status_code == 403
