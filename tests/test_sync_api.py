from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_sync_run_response_schema(monkeypatch) -> None:
    async def fake_refresh_enabled_channels() -> dict:
        return {
            "channels_seen": 3,
            "resolved": 1,
            "synced": 2,
            "failed": 1,
            "failures": [{"id": 5, "input": "@missing", "error": "Unable to resolve handle"}],
        }

    monkeypatch.setattr(
        "app.api.routes_sync.refresh_enabled_channels",
        fake_refresh_enabled_channels,
    )

    with TestClient(app) as client:
        response = client.post("/api/sync/run")

    assert response.status_code == 200
    assert response.json() == {
        "channels_seen": 3,
        "resolved": 1,
        "synced": 2,
        "failed": 1,
        "failures": [{"id": 5, "input": "@missing", "error": "Unable to resolve handle"}],
    }
