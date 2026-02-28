from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready() -> None:
    with TestClient(app) as client:
        response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"ready": True}



def test_system_details() -> None:
    with TestClient(app) as client:
        response = client.get("/api/system")
    assert response.status_code == 200
    payload = response.json()
    expected = {"db_path", "db_exists", "db_size_bytes", "uptime_seconds", "app_version"}
    assert expected.issubset(payload)
