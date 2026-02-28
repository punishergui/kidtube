from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, create_engine

from app.db.migrate import run_migrations
from app.db.session import get_session
from app.main import app
from app.services.limits import is_in_any_schedule


def _client_for_engine(engine):
    def get_test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    return TestClient(app)


def test_search_returns_results_shape_and_logs(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "phase12-search.db"
    engine = create_engine(f"sqlite:///{db_path}")
    run_migrations(engine, Path("app/db/migrations"))

    with Session(engine) as session:
        session.execute(text("INSERT INTO kids(name) VALUES ('Ava')"))
        session.commit()

    async def fake_search_videos(query: str, max_results: int = 12, client=None):
        del max_results, client
        assert query == "cats"
        return [
            {
                "video_id": "abc123xyz99",
                "title": "Cats",
                "channel_id": "UC123",
                "channel_title": "CatTV",
                "thumbnail_url": "https://img",
                "published_at": "2024-01-01T00:00:00Z",
                "duration_seconds": 50,
                "is_short": True,
            }
        ]

    monkeypatch.setattr("app.api.routes_search.search_videos", fake_search_videos)

    try:
        with _client_for_engine(engine) as client:
            response = client.get("/api/search?q=cats&kid_id=1")
            logs = client.get("/api/logs/search")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["video_id"] == "abc123xyz99"
    assert payload[0]["is_short"] is True

    assert logs.status_code == 200
    assert logs.json()[0]["kid_name"] == "Ava"


def test_category_delete_or_archive_when_used(tmp_path: Path) -> None:
    db_path = tmp_path / "phase12-category.db"
    engine = create_engine(f"sqlite:///{db_path}")
    run_migrations(engine, Path("app/db/migrations"))

    with Session(engine) as session:
        session.execute(
            text("INSERT INTO categories(name, enabled) VALUES ('Used', 1), ('Unused', 1)")
        )
        session.execute(
            text(
                "INSERT INTO channels(youtube_id, title, category_id, resolve_status) "
                "VALUES ('UCX', 'X', 1, 'ok')"
            )
        )
        session.commit()

    try:
        with _client_for_engine(engine) as client:
            conflict = client.delete("/api/categories/1")
            archived = client.delete("/api/categories/1?archive=true")
            deleted = client.delete("/api/categories/2?hard_delete=true")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert conflict.status_code == 409
    assert archived.status_code == 200
    assert archived.json()["enabled"] is False
    assert deleted.status_code == 200


def test_recent_logs_include_kid_name(tmp_path: Path) -> None:
    db_path = tmp_path / "phase12-recent.db"
    engine = create_engine(f"sqlite:///{db_path}")
    run_migrations(engine, Path("app/db/migrations"))

    with Session(engine) as session:
        session.execute(text("INSERT INTO kids(name) VALUES ('Luna')"))
        session.execute(
            text(
                "INSERT INTO channels(youtube_id, title, resolve_status, allowed) "
                "VALUES ('UC1', 'ABC', 'ok', 1)"
            )
        )
        session.execute(
            text(
                "INSERT INTO videos(youtube_id, channel_id, title, thumbnail_url, published_at) "
                "VALUES ('vid12345678A', 1, 'Hi', 'https://img', '2024-01-01T00:00:00Z')"
            )
        )
        session.execute(
            text(
                "INSERT INTO watch_log(kid_id, video_id, seconds_watched, created_at) "
                "VALUES (1, 1, 40, '2024-01-01T01:00:00Z')"
            )
        )
        session.commit()

    try:
        with _client_for_engine(engine) as client:
            response = client.get("/api/logs/recent?kid_id=1&limit=10")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    assert response.json()[0]["kid_name"] == "Luna"


def test_schedule_serialization_and_enforcement(tmp_path: Path) -> None:
    db_path = tmp_path / "phase12-schedule.db"
    engine = create_engine(f"sqlite:///{db_path}")
    run_migrations(engine, Path("app/db/migrations"))

    with Session(engine) as session:
        session.execute(text("INSERT INTO kids(name) VALUES ('Noah')"))
        session.execute(
            text(
                "INSERT INTO kid_schedules(kid_id, day_of_week, start_time, end_time) "
                "VALUES (1, 6, '09:00', '10:00')"
            )
        )
        session.commit()

        sunday = datetime(2024, 6, 2, 9, 30, tzinfo=timezone.utc)  # noqa: UP017
        monday = datetime(2024, 6, 3, 9, 30, tzinfo=timezone.utc)  # noqa: UP017
        assert is_in_any_schedule(session, kid_id=1, now=sunday) is True
        assert is_in_any_schedule(session, kid_id=1, now=monday) is True


def test_watch_logs_endpoint_includes_kid_name(tmp_path: Path) -> None:
    db_path = tmp_path / "phase12-watch-logs.db"
    engine = create_engine(f"sqlite:///{db_path}")
    run_migrations(engine, Path("app/db/migrations"))

    with Session(engine) as session:
        session.execute(text("INSERT INTO kids(name) VALUES ('Piper')"))
        session.execute(
            text(
                "INSERT INTO channels(youtube_id, title, resolve_status, allowed) "
                "VALUES ('UCWATCH', 'Watch Ch', 'ok', 1)"
            )
        )
        session.execute(
            text(
                "INSERT INTO videos(youtube_id, channel_id, title, thumbnail_url, published_at) "
                "VALUES ('vidwatch001', 1, 'Watch me', 'https://img', '2024-01-01T00:00:00Z')"
            )
        )
        session.execute(
            text(
                "INSERT INTO watch_log(kid_id, video_id, seconds_watched, created_at) "
                "VALUES (1, 1, 30, '2024-01-01T01:00:00Z')"
            )
        )
        session.commit()

    try:
        with _client_for_engine(engine) as client:
            response = client.get('/api/logs/watch?limit=10')
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    assert response.json()[0]['kid_name'] == 'Piper'
