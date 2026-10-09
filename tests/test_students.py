from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.enums import UserRole
from backend.modules.feedback.models import EvaluatorComment, StudentFeedback
from tests.conftest import EvaluationFactory, UserFactory, auth_headers

DIMENSIONS = {"ease_of_use": 5, "clarity": 4, "usefulness": 5, "interaction": 3, "satisfaction": 4}


def feedback_path(evaluation_id: int) -> str:
    return f"/students/evaluations/{evaluation_id}/feedback"


def comments_path(evaluation_id: int) -> str:
    return f"/students/evaluations/{evaluation_id}/comments"


def feedback_payload(*, rating: int = 4, comment: str | None = None) -> dict[str, Any]:
    return {"rating": rating, "dimension_ratings": DIMENSIONS, "comment": comment}


def test_submits_feedback(
    client: TestClient, create_user: UserFactory, create_evaluation: EvaluationFactory
) -> None:
    student = create_user()
    evaluation = create_evaluation(student)

    response = client.post(
        feedback_path(evaluation.evaluation_id),
        json=feedback_payload(comment="Muy útil"),
        headers=auth_headers(student),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["evaluation_id"] == evaluation.evaluation_id
    assert body["user_id"] == student.user_id
    assert body["rating"] == 4
    assert body["dimension_ratings"] == DIMENSIONS
    assert body["comment"] == "Muy útil"


def test_resubmitting_updates_without_duplicating_or_erasing_comment(
    client: TestClient,
    session: Session,
    create_user: UserFactory,
    create_evaluation: EvaluationFactory,
) -> None:
    student = create_user()
    evaluation = create_evaluation(student)
    path = feedback_path(evaluation.evaluation_id)
    first = client.post(
        path, json=feedback_payload(comment="Primero"), headers=auth_headers(student)
    )

    second = client.post(path, json=feedback_payload(rating=2), headers=auth_headers(student))

    assert second.status_code == 200
    assert second.json()["feedback_id"] == first.json()["feedback_id"]
    assert second.json()["rating"] == 2
    assert second.json()["comment"] == "Primero"
    assert session.scalar(select(func.count()).select_from(StudentFeedback)) == 1


def test_patch_updates_and_clears_comment(
    client: TestClient, create_user: UserFactory, create_evaluation: EvaluationFactory
) -> None:
    student = create_user()
    evaluation = create_evaluation(student)
    path = feedback_path(evaluation.evaluation_id)
    client.post(path, json=feedback_payload(), headers=auth_headers(student))

    updated = client.patch(path, json={"comment": "Nuevo"}, headers=auth_headers(student))
    cleared = client.patch(path, json={"comment": None}, headers=auth_headers(student))

    assert updated.status_code == 200
    assert updated.json()["comment"] == "Nuevo"
    assert cleared.status_code == 200
    assert cleared.json()["comment"] is None
    assert cleared.json()["rating"] == 4


def test_patch_requires_previous_rating(
    client: TestClient, create_user: UserFactory, create_evaluation: EvaluationFactory
) -> None:
    student = create_user()
    evaluation = create_evaluation(student)

    response = client.patch(
        feedback_path(evaluation.evaluation_id),
        json={"comment": "Hola"},
        headers=auth_headers(student),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Primero envía tu calificación"}


def test_reads_own_feedback(
    client: TestClient, create_user: UserFactory, create_evaluation: EvaluationFactory
) -> None:
    student = create_user()
    evaluation = create_evaluation(student)
    path = feedback_path(evaluation.evaluation_id)
    submitted = client.post(path, json=feedback_payload(), headers=auth_headers(student))

    response = client.get(path, headers=auth_headers(student))

    assert response.status_code == 200
    assert response.json() == submitted.json()


def test_reading_missing_feedback_returns_404(
    client: TestClient, create_user: UserFactory, create_evaluation: EvaluationFactory
) -> None:
    student = create_user()
    evaluation = create_evaluation(student)

    response = client.get(feedback_path(evaluation.evaluation_id), headers=auth_headers(student))

    assert response.status_code == 404
    assert response.json() == {"detail": "Feedback no encontrado"}


def test_rejects_evaluation_of_another_student(
    client: TestClient, create_user: UserFactory, create_evaluation: EvaluationFactory
) -> None:
    evaluation = create_evaluation(create_user(email="duenio@kairos.dev"))
    path = feedback_path(evaluation.evaluation_id)
    headers = auth_headers(create_user())

    responses = [
        client.post(path, json=feedback_payload(), headers=headers),
        client.patch(path, json={"comment": "x"}, headers=headers),
        client.get(path, headers=headers),
    ]

    for response in responses:
        assert response.status_code == 404
        assert response.json() == {"detail": "Evaluación no encontrada"}


def test_rejects_rating_out_of_range(
    client: TestClient, create_user: UserFactory, create_evaluation: EvaluationFactory
) -> None:
    student = create_user()
    evaluation = create_evaluation(student)

    response = client.post(
        feedback_path(evaluation.evaluation_id),
        json=feedback_payload(rating=6),
        headers=auth_headers(student),
    )

    assert response.status_code == 422


def test_evaluator_cannot_submit_feedback(
    client: TestClient, create_user: UserFactory, create_evaluation: EvaluationFactory
) -> None:
    evaluation = create_evaluation(create_user())
    evaluator = create_user(email="evaluador@kairos.dev", role=UserRole.EVALUATOR)

    response = client.post(
        feedback_path(evaluation.evaluation_id),
        json=feedback_payload(),
        headers=auth_headers(evaluator),
    )

    assert response.status_code == 403


def test_lists_evaluator_comments_newest_first(
    client: TestClient,
    session: Session,
    create_user: UserFactory,
    create_evaluation: EvaluationFactory,
) -> None:
    student = create_user()
    evaluator = create_user(email="evaluador@kairos.dev", role=UserRole.EVALUATOR)
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

    response = client.get(comments_path(evaluation.evaluation_id), headers=auth_headers(student))

    assert response.status_code == 200
    body = response.json()
    assert [item["comment_text"] for item in body] == ["reciente", "antiguo"]
    assert body[0]["evaluator_name"] == evaluator.full_name
    assert "evaluator_id" not in body[0]


def test_lists_no_comments(
    client: TestClient, create_user: UserFactory, create_evaluation: EvaluationFactory
) -> None:
    student = create_user()
    evaluation = create_evaluation(student)

    response = client.get(comments_path(evaluation.evaluation_id), headers=auth_headers(student))

    assert response.status_code == 200
    assert response.json() == []


def test_rejects_comments_of_another_student(
    client: TestClient, create_user: UserFactory, create_evaluation: EvaluationFactory
) -> None:
    evaluation = create_evaluation(create_user(email="duenio@kairos.dev"))

    response = client.get(
        comments_path(evaluation.evaluation_id), headers=auth_headers(create_user())
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Evaluación no encontrada"}


def test_evaluator_cannot_use_student_comments_endpoint(
    client: TestClient, create_user: UserFactory, create_evaluation: EvaluationFactory
) -> None:
    evaluation = create_evaluation(create_user())
    evaluator = create_user(email="evaluador@kairos.dev", role=UserRole.EVALUATOR)

    response = client.get(comments_path(evaluation.evaluation_id), headers=auth_headers(evaluator))

    assert response.status_code == 403
