import pytest
from fastapi.testclient import TestClient

TEST_SCORES = {"R": 2.04, "I": 4.96, "A": 3.0, "S": 2.5, "E": 1.0, "C": 3.5}


def test_recommends_from_test_scores(client: TestClient) -> None:
    response = client.post("/recomendar-por-test", json=TEST_SCORES)

    assert response.status_code == 200
    body = response.json()
    assert body["riasec_profile"] == {"R": 2.0, "I": 5.0, "A": 3.0, "S": 2.5, "E": 1.0, "C": 3.5}
    assert len(body["top3_careers"]) == 3
    assert set(body["top3_careers"][0]) == {"career", "score", "description", "faculty"}


def test_rejects_scores_outside_likert_range(client: TestClient) -> None:
    response = client.post("/recomendar-por-test", json={**TEST_SCORES, "R": 6})

    assert response.status_code == 422


def test_recommends_from_chat_text(client: TestClient) -> None:
    response = client.post(
        "/recomendar-por-chat", json={"texto": "me gusta programar y resolver problemas"}
    )

    assert response.status_code == 200
    profile = response.json()["riasec_profile"]
    assert max(profile, key=profile.get) == "I"
    assert all(1.0 <= value <= 5.0 for value in profile.values())


@pytest.mark.parametrize("payload", [{"texto": ""}, {}])
def test_rejects_empty_chat_text(client: TestClient, payload: dict) -> None:
    assert client.post("/recomendar-por-chat", json=payload).status_code == 422


def test_endpoints_are_public(client: TestClient) -> None:
    response = client.post("/recomendar-por-test", json=TEST_SCORES, headers={})

    assert response.status_code == 200
