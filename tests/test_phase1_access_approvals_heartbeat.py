from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, create_engine

from app.db.migrate import run_migrations
from app.db.models import Channel, Kid, Request, Video
from app.db.session import get_session
from app.main import app
from app.services.limits import (
    ACCESS_REASON_BLOCKED_CHANNEL,
    ACCESS_REASON_DAILY_LIMIT,
    ACCESS_REASON_PENDING_APPROVAL,
    ACCESS_REASON_SCHEDULE,
    ACCESS_REASON_SHORTS_DISABLED,
    check_access,
)


def _client_for_engine(engine):
    def get_test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    return TestClient(app)


def test_check_access_daily_limit_reached(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'phase1-limit.db'}")
    run_migrations(engine, Path("app/db/migrations"))

    now = datetime.now(timezone.utc)  # noqa: UP017
    with Session(engine) as session:
        kid = Kid(name="A", daily_limit_minutes=1)
        channel = Channel(
            youtube_id="UCLIM", allowed=True, enabled=True, blocked=False, resolve_status="ok"
        )
        session.add(kid)
        session.add(channel)
        session.commit()
        session.refresh(kid)
        session.refresh(channel)

        video = Video(
            youtube_id="vid-limit-1",
            channel_id=channel.id,
            title="Learning",
            thumbnail_url="https://img",
            published_at=now,
        )
        session.add(video)
        session.commit()

        session.execute(
            text(
                """
                INSERT INTO watch_log(kid_id, video_id, seconds_watched, started_at, created_at)
                VALUES (:kid_id, :video_id, 60, :now, :now)
                """
            ),
            {"kid_id": kid.id, "video_id": video.id, "now": now.isoformat()},
        )
        session.commit()

        allowed, reason, _details = check_access(session, kid.id, video_id="vid-limit-1", now=now)

    assert allowed is False
    assert reason == ACCESS_REASON_DAILY_LIMIT


def test_check_access_outside_schedule(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'phase1-schedule.db'}")
    run_migrations(engine, Path("app/db/migrations"))

    with Session(engine) as session:
        kid = Kid(name="B")
        session.add(kid)
        session.commit()
        session.refresh(kid)
        day = datetime.now(timezone.utc).weekday()  # noqa: UP017
        session.execute(
            text(
                """
                INSERT INTO kid_schedules(kid_id, day_of_week, start_time, end_time)
                VALUES (:kid_id, :day, '00:00', '00:01')
                """
            ),
            {"kid_id": kid.id, "day": day},
        )
        session.commit()
        now = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)  # noqa: UP017
        allowed, reason, _details = check_access(session, kid.id, now=now)

    assert allowed is False
    assert reason == ACCESS_REASON_SCHEDULE


def test_check_access_shorts_disabled(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'phase1-shorts.db'}")
    run_migrations(engine, Path("app/db/migrations"))

    with Session(engine) as session:
        kid = Kid(name="C")
        session.add(kid)
        session.commit()
        session.refresh(kid)
        session.execute(text("UPDATE parent_settings SET shorts_enabled = 0 WHERE id = 1"))
        session.commit()

        allowed, reason, _details = check_access(session, kid.id, is_shorts=True)

    assert allowed is False
    assert reason == ACCESS_REASON_SHORTS_DISABLED


def test_check_access_pending_request_blocks_video(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'phase1-pending.db'}")
    run_migrations(engine, Path("app/db/migrations"))

    now = datetime.now(timezone.utc)  # noqa: UP017
    with Session(engine) as session:
        kid = Kid(name="D")
        channel = Channel(
            youtube_id="UCPEND", allowed=False, enabled=True, blocked=False, resolve_status="ok"
        )
        session.add(kid)
        session.add(channel)
        session.commit()
        session.refresh(kid)
        session.refresh(channel)
        session.add(
            Video(
                youtube_id="vid-pending-1",
                channel_id=channel.id,
                title="Pending video",
                thumbnail_url="https://img",
                published_at=now,
            )
        )
        session.add(
            Request(type="video", youtube_id="vid-pending-1", kid_id=kid.id, status="pending")
        )
        session.commit()

        allowed, reason, _details = check_access(session, kid.id, video_id="vid-pending-1")

    assert allowed is False
    assert reason == ACCESS_REASON_PENDING_APPROVAL


def test_check_access_blocked_channel(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'phase1-blocked-channel.db'}")
    run_migrations(engine, Path("app/db/migrations"))

    now = datetime.now(timezone.utc)  # noqa: UP017
    with Session(engine) as session:
        kid = Kid(name="E")
        channel = Channel(
            youtube_id="UCBLOCK", allowed=True, enabled=True, blocked=True, resolve_status="ok"
        )
        session.add(kid)
        session.add(channel)
        session.commit()
        session.refresh(kid)
        session.refresh(channel)
        session.add(
            Video(
                youtube_id="vid-blocked-1",
                channel_id=channel.id,
                title="Blocked video",
                thumbnail_url="https://img",
                published_at=now,
            )
        )
        session.commit()

        allowed, reason, _details = check_access(session, kid.id, video_id="vid-blocked-1")

    assert allowed is False
    assert reason == ACCESS_REASON_BLOCKED_CHANNEL


def test_approvals_endpoints_and_heartbeat(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'phase1-api.db'}")
    run_migrations(engine, Path("app/db/migrations"))

    now = datetime.now(timezone.utc)  # noqa: UP017
    with Session(engine) as session:
        kid = Kid(name="Finn")
        channel = Channel(
            youtube_id="UCAPI1", allowed=False, enabled=True, blocked=False, resolve_status="ok"
        )
        session.add(kid)
        session.add(channel)
        session.commit()
        session.refresh(kid)
        session.refresh(channel)
        video = Video(
            youtube_id="vid-api-1",
            channel_id=channel.id,
            title="API Video",
            thumbnail_url="https://img",
            published_at=now,
        )
        session.add(video)
        session.commit()
        session.refresh(video)

    try:
        with _client_for_engine(engine) as client:
            create_req = client.post(
                "/api/requests/channel-allow", json={"youtube_id": "UCAPI1", "kid_id": 1}
            )
            request_id = create_req.json()["id"]
            list_pending = client.get("/api/requests", params={"status": "pending"})
            approve = client.post(f"/api/requests/{request_id}/approve")
            heartbeat1 = client.post(
                "/api/playback/watch/log",
                json={"kid_id": 1, "video_id": "vid-api-1", "seconds_delta": 12},
            )
            heartbeat2 = client.post(
                "/api/playback/watch/log",
                json={"kid_id": 1, "video_id": "vid-api-1", "seconds_delta": 12},
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert create_req.status_code == 201
    assert list_pending.status_code == 200
    assert any(row["id"] == request_id for row in list_pending.json())
    assert approve.status_code == 200
    assert heartbeat1.status_code == 200
    assert heartbeat2.status_code == 200

    with Session(engine) as session:
        channel_allowed = session.execute(
            text("SELECT allowed FROM channels WHERE youtube_id = 'UCAPI1' LIMIT 1")
        ).one()[0]
        log_count = session.execute(text("SELECT COUNT(*) FROM watch_log WHERE kid_id = 1")).one()[
            0
        ]

    assert int(channel_allowed) == 1
    assert int(log_count) == 1
