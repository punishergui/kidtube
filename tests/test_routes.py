from fastapi.testclient import TestClient

from app.main import app


def test_api_routes_are_mounted() -> None:
    with TestClient(app) as client:
        feed_response = client.get("/api/feed/latest-per-channel")
        channels_response = client.get("/api/channels")

    assert feed_response.status_code != 404
    assert channels_response.status_code != 404
