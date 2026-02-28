from __future__ import annotations

from datetime import datetime
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


def test_playback_log_records_category_id_from_video_channel(tmp_path: Path) -> None:
    db_path = tmp_path / "playback-log-test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    run_migrations(engine, Path("app/db/migrations"))

    with Session(engine) as session:
        fun = session.execute(text("SELECT id FROM categories WHERE name = 'fun'")).one()[0]
        kid_id = session.execute(text("INSERT INTO kids(name) VALUES ('Noah')")).lastrowid

        channel = Channel(
            youtube_id="UCplaylog0000000000000000",
            title="Play Log",
            category="fun",
            category_id=fun,
            resolve_status="ok",
            allowed=True,
        )
        session.add(channel)
        session.commit()
        session.refresh(channel)

        session.add(
            Video(
                youtube_id="vid-play-log",
                channel_id=channel.id,
                title="Play log video",
                thumbnail_url="https://img.example/play-log.jpg",
                published_at=datetime.now(datetime.UTC),
            )
        )
        session.commit()

    try:
        with _test_client_for_engine(engine) as client:
            response = client.post(
                "/api/playback/log",
                json={
                    "kid_id": kid_id,
                    "youtube_id": "vid-play-log",
                    "seconds_watched": 30,
                },
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    assert response.json() == {"ok": True}

    with Session(engine) as session:
        row = session.execute(
            text(
                """
                SELECT category_id, seconds_watched
                FROM watch_log
                WHERE kid_id = :kid_id
                LIMIT 1
                """
            ),
            {"kid_id": kid_id},
        ).one()

    assert row[0] == fun
    assert row[1] == 30


def test_video_lookup_returns_403_when_kid_over_category_limit(tmp_path: Path) -> None:
    db_path = tmp_path / "video-limit-test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    run_migrations(engine, Path("app/db/migrations"))

    now = datetime.now(datetime.UTC)

    with Session(engine) as session:
        fun = session.execute(text("SELECT id FROM categories WHERE name = 'fun'")).one()[0]
        kid_id = session.execute(
            text("INSERT INTO kids(name, daily_limit_minutes) VALUES ('Ari', 30)")
        ).lastrowid

        channel = Channel(
            youtube_id="UCvidlimit000000000000000",
            title="Limit",
            category="fun",
            category_id=fun,
            resolve_status="ok",
            allowed=True,
        )
        session.add(channel)
        session.commit()
        session.refresh(channel)

        video = Video(
            youtube_id="vid-over-limit",
            channel_id=channel.id,
            title="Too much",
            thumbnail_url="https://img.example/limit.jpg",
            published_at=now,
        )
        session.add(video)
        session.commit()
        session.refresh(video)

        session.execute(
            text(
                """
                INSERT INTO kid_category_limits(kid_id, category_id, daily_limit_minutes)
                VALUES (:kid_id, :category_id, 1)
                """
            ),
            {"kid_id": kid_id, "category_id": fun},
        )
        session.execute(
            text(
                """
                INSERT INTO watch_log(
                    kid_id, video_id, seconds_watched, category_id, started_at, created_at
                )
                VALUES (:kid_id, :video_id, 60, :category_id, :started_at, :created_at)
                """
            ),
            {
                "kid_id": kid_id,
                "video_id": video.id,
                "category_id": fun,
                "started_at": now.isoformat(),
                "created_at": now.isoformat(),
            },
        )
        session.commit()

    try:
        with _test_client_for_engine(engine) as client:
            response = client.get(f"/api/videos/vid-over-limit?kid_id={kid_id}")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 403
    assert response.json() == {"detail": "Daily watch limit reached"}
