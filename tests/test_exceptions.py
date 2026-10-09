from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_validation_error_returns_spanish_detail() -> None:
    response = client.post("/signup", json={"email": "sin-arroba"})

    assert response.status_code == 422
    assert response.json()["detail"] == "Los datos enviados no son válidos"
    assert response.json()["errors"]


def test_unknown_route_returns_spanish_detail() -> None:
    response = client.get("/ruta-inexistente")

    assert response.status_code == 404
    assert response.json() == {"detail": "Recurso no encontrado"}


def test_wrong_method_returns_spanish_detail() -> None:
    response = client.delete("/health")

    assert response.status_code == 405
    assert response.json() == {"detail": "Método no permitido"}
