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


def _test_client_for_engine(engine):
    def get_test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    return TestClient(app)


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

    now = datetime.now(timezone.utc)  # noqa: UP017

    with Session(engine) as session:
        session.exec(text("DELETE FROM videos"))
        session.exec(text("DELETE FROM channels"))
        session.commit()

        c1 = Channel(
            youtube_id="UC1234567890123456789012",
            title="Alpha",
            category="education",
            resolve_status="ok",
            allowed=True,
            blocked=False,
        )
        c2 = Channel(
            youtube_id="UCabcdefghijklmno123456",
            title="Beta",
            category="fun",
            resolve_status="ok",
            allowed=True,
            blocked=False,
        )
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
        with _test_client_for_engine(engine) as client:
            response = client.get("/api/feed/latest-per-channel")
            full_feed = client.get("/api/feed?limit=2&offset=0")
            filtered = client.get(f"/api/feed?channel_id={c1.id}&category=education")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert payload[0]["video_youtube_id"] == "vid00000002"
    assert payload[1]["video_youtube_id"] == "vid00000003"

    assert full_feed.status_code == 200
    assert [item["video_youtube_id"] for item in full_feed.json()] == ["vid00000002", "vid00000003"]

    assert filtered.status_code == 200
    assert [item["video_youtube_id"] for item in filtered.json()] == ["vid00000002", "vid00000001"]


def test_feed_respects_allowed_and_blocked_flags(tmp_path: Path) -> None:
    db_path = tmp_path / "feed-flags-test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    run_migrations(engine, Path("app/db/migrations"))

    now = datetime.now(timezone.utc)  # noqa: UP017

    with Session(engine) as session:
        c_allowed = Channel(
            youtube_id="UCallow00000000000000000",
            title="Allowed",
            resolve_status="ok",
            allowed=True,
        )
        c_not_allowed = Channel(
            youtube_id="UCdeny0000000000000000000",
            title="NotAllowed",
            resolve_status="ok",
            allowed=False,
        )
        c_blocked = Channel(
            youtube_id="UCblock000000000000000000",
            title="Blocked",
            resolve_status="ok",
            allowed=True,
            blocked=True,
        )
        session.add(c_allowed)
        session.add(c_not_allowed)
        session.add(c_blocked)
        session.commit()
        session.refresh(c_allowed)
        session.refresh(c_not_allowed)
        session.refresh(c_blocked)

        session.add(
            Video(
                youtube_id="vid-allowed",
                channel_id=c_allowed.id,
                title="Allowed Video",
                thumbnail_url="https://img.example/allowed.jpg",
                published_at=now,
            )
        )
        session.add(
            Video(
                youtube_id="vid-not-allowed",
                channel_id=c_not_allowed.id,
                title="Not Allowed Video",
                thumbnail_url="https://img.example/not-allowed.jpg",
                published_at=now - timedelta(minutes=1),
            )
        )
        session.add(
            Video(
                youtube_id="vid-blocked",
                channel_id=c_blocked.id,
                title="Blocked Video",
                thumbnail_url="https://img.example/blocked.jpg",
                published_at=now - timedelta(minutes=2),
            )
        )
        session.commit()

    try:
        with _test_client_for_engine(engine) as client:
            response = client.get("/api/feed/latest-per-channel")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    payload = response.json()
    assert [item["video_youtube_id"] for item in payload] == ["vid-allowed"]


def test_blocking_channel_purges_cached_videos_and_delete_channel(tmp_path: Path) -> None:
    db_path = tmp_path / "feed-block-purge-test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    run_migrations(engine, Path("app/db/migrations"))

    now = datetime.now(timezone.utc)  # noqa: UP017

    with Session(engine) as session:
        channel = Channel(
            youtube_id="UCpurge000000000000000000",
            title="Purge",
            resolve_status="ok",
            allowed=True,
        )
        session.add(channel)
        session.commit()
        session.refresh(channel)
        channel_id = channel.id

        session.add(
            Video(
                youtube_id="vid-purge",
                channel_id=channel_id,
                title="Purge Me",
                thumbnail_url="https://img.example/purge.jpg",
                published_at=now,
            )
        )
        session.commit()

    try:
        with _test_client_for_engine(engine) as client:
            response = client.patch(
                f"/api/channels/{channel_id}",
                json={"blocked": True, "blocked_reason": "Unsafe content"},
            )
            delete_response = client.delete(f"/api/channels/{channel_id}")
            feed_response = client.get("/api/feed/latest-per-channel")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    patched = response.json()
    assert patched["blocked"] is True
    assert patched["blocked_reason"] == "Unsafe content"
    assert delete_response.status_code == 204

    with Session(engine) as session:
        channel_count = session.execute(
            text("SELECT COUNT(*) FROM channels WHERE id = :id"),
            {"id": channel_id},
        ).one()[0]
        remaining = session.execute(
            text("SELECT COUNT(*) FROM videos WHERE channel_id = :channel_id"),
            {"channel_id": channel_id},
        ).one()[0]
    assert channel_count == 0
    assert remaining == 0

    assert feed_response.status_code == 200
    assert feed_response.json() == []
