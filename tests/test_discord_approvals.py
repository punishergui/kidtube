from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, create_engine

from app.db.migrate import run_migrations
from app.db.models import Channel, Kid, Request, Video
from app.db.session import get_session
from app.main import app


def _client_for_engine(engine):
    def get_test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    return TestClient(app)


def test_request_creation_endpoints_write_db_rows(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "request-create.db"
    engine = create_engine(f"sqlite:///{db_path}")
    run_migrations(engine, Path("app/db/migrations"))

    monkeypatch.setattr("app.api.routes_requests.settings.discord_approval_webhook_url", None)

    with Session(engine) as session:
        kid = Kid(name="Mia")
        session.add(kid)
        session.commit()
        session.refresh(kid)
        kid_id = kid.id

    try:
        with _client_for_engine(engine) as client:
            channel_response = client.post(
                "/api/requests/channel-allow",
                json={"youtube_id": "UCallow123456789012345678", "kid_id": kid_id},
            )
            video_response = client.post(
                "/api/requests/video-allow", json={"youtube_id": "vidallow1234", "kid_id": kid_id}
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert channel_response.status_code == 201
    assert video_response.status_code == 201

    with Session(engine) as session:
        rows = session.execute(
            text("SELECT type, youtube_id, kid_id, status FROM requests ORDER BY id")
        ).all()

    assert rows == [
        ("channel", "UCallow123456789012345678", kid_id, "pending"),
        ("video", "vidallow1234", kid_id, "pending"),
    ]


def test_discord_approve_updates_db(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "discord-approve.db"
    engine = create_engine(f"sqlite:///{db_path}")
    run_migrations(engine, Path("app/db/migrations"))

    monkeypatch.setattr("app.api.routes_discord.settings.discord_public_key", "00" * 32)
    monkeypatch.setattr("app.api.routes_discord._verify_signature", lambda *args, **kwargs: None)

    with Session(engine) as session:
        kid = Kid(name="Noah")
        channel = Channel(youtube_id="UCapprove0000000000000000", title="Approve Me")
        video_channel = Channel(youtube_id="UCvideo0000000000000000000", title="Video Home")
        session.add(kid)
        session.add(channel)
        session.add(video_channel)
        session.commit()
        session.refresh(kid)
        kid_id = kid.id

        session.add(
            Video(
                youtube_id="vidapprove11",
                channel_id=video_channel.id,
                title="Needs Approval",
                thumbnail_url="https://img.example/approval.jpg",
                published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),  # noqa: UP017
            )
        )

        session.add(Request(type="channel", youtube_id=channel.youtube_id, kid_id=kid.id))
        session.add(Request(type="video", youtube_id="vidapprove11", kid_id=kid.id))
        session.add(Request(type="bonus", youtube_id="30", kid_id=kid.id))
        session.commit()

    headers = {
        "X-Signature-Ed25519": "00" * 64,
        "X-Signature-Timestamp": "1700000000",
    }

    try:
        with _client_for_engine(engine) as client:
            resp_channel = client.post(
                "/discord/interactions",
                headers=headers,
                content=json.dumps({"type": 3, "data": {"custom_id": "request:1:approve"}}),
            )
            resp_video = client.post(
                "/discord/interactions",
                headers=headers,
                content=json.dumps({"type": 3, "data": {"custom_id": "request:2:approve"}}),
            )
            resp_bonus = client.post(
                "/discord/interactions",
                headers=headers,
                content=json.dumps({"type": 3, "data": {"custom_id": "request:3:approve"}}),
            )
            resp_bonus_direct = client.post(
                "/discord/interactions",
                headers=headers,
                content=json.dumps({"type": 3, "data": {"custom_id": f"bonus:{kid_id}:15"}}),
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp_channel.status_code == 200
    assert resp_video.status_code == 200
    assert resp_bonus.status_code == 200
    assert resp_bonus_direct.status_code == 200

    with Session(engine) as session:
        channel_allowed = session.execute(
            text("SELECT allowed FROM channels WHERE youtube_id = :youtube_id"),
            {"youtube_id": "UCapprove0000000000000000"},
        ).one()[0]
        video_approvals = session.execute(text("SELECT COUNT(*) FROM video_approvals")).one()[0]
        approved_requests = session.execute(
            text("SELECT COUNT(*) FROM requests WHERE status = 'approved'")
        ).one()[0]
        bonus_total = session.execute(
            text("SELECT SUM(minutes) FROM kid_bonus_time WHERE kid_id = :kid_id"),
            {"kid_id": kid_id},
        ).one()[0]

    assert channel_allowed == 1
    assert video_approvals == 1
    assert approved_requests == 3
    assert bonus_total == 45
