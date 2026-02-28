from fastapi.testclient import TestClient

from app.main import app


def test_request_id_header_generated_when_missing() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")


def test_request_id_header_echoes_client_header() -> None:
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "abc-123"})

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "abc-123"
