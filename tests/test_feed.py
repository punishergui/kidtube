from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, create_engine

from app.db.migrate import run_migrations
from app.db.models import Channel, Video
from app.db.session import get_session
from app.main import app


def test_latest_per_channel_uses_cached_db_only(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "app.services.youtube.fetch_latest_videos",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("network disabled")),
    )
    monkeypatch.setattr(
        "app.services.youtube.fetch_channel_metadata",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("network disabled")),
    )

    db_path = tmp_path / "feed-test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    run_migrations(engine, Path("app/db/migrations"))

    def get_test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session

    now = datetime.now(timezone.utc)  # noqa: UP017

    with Session(engine) as session:
        session.exec(text("DELETE FROM videos"))
        session.exec(text("DELETE FROM channels"))
        session.commit()

        c1 = Channel(youtube_id="UC1234567890123456789012", title="Alpha", resolve_status="ok")
        c2 = Channel(youtube_id="UCabcdefghijklmno123456", title="Beta", resolve_status="ok")
        session.add(c1)
        session.add(c2)
        session.commit()
        session.refresh(c1)
        session.refresh(c2)

        session.add(
            Video(
                youtube_id="vid00000001",
                channel_id=c1.id,
                title="old",
                thumbnail_url="https://img.example/1.jpg",
                published_at=now - timedelta(days=1),
            )
        )
        session.add(
            Video(
                youtube_id="vid00000002",
                channel_id=c1.id,
                title="new",
                thumbnail_url="https://img.example/2.jpg",
                published_at=now,
            )
        )
        session.add(
            Video(
                youtube_id="vid00000003",
                channel_id=c2.id,
                title="beta",
                thumbnail_url="https://img.example/3.jpg",
                published_at=now - timedelta(hours=2),
            )
        )
        session.commit()

    try:
        with TestClient(app) as client:
            response = client.get("/api/feed/latest-per-channel")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert payload[0]["video_youtube_id"] == "vid00000002"
    assert payload[1]["video_youtube_id"] == "vid00000003"
