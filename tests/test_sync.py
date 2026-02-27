from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, create_engine

from app.db.migrate import run_migrations
from app.db.models import Channel
from app.services.sync import select_sync_channel_ids


def test_select_sync_channel_ids_excludes_blocked_and_not_allowed(tmp_path: Path) -> None:
    db_path = tmp_path / "sync-selection.db"
    engine = create_engine(f"sqlite:///{db_path}")
    run_migrations(engine, Path("app/db/migrations"))

    with Session(engine) as session:
        allowed_channel = Channel(
            youtube_id="UCsync-allowed",
            resolve_status="ok",
            enabled=True,
            allowed=True,
            blocked=False,
        )
        session.add(allowed_channel)
        session.add(
            Channel(
                youtube_id="UCsync-blocked",
                resolve_status="ok",
                enabled=True,
                allowed=True,
                blocked=True,
            )
        )
        session.add(
            Channel(
                youtube_id="UCsync-notallowed",
                resolve_status="ok",
                enabled=True,
                allowed=False,
                blocked=False,
            )
        )
        session.add(
            Channel(
                youtube_id="UCsync-disabled",
                resolve_status="ok",
                enabled=False,
                allowed=True,
                blocked=False,
            )
        )
        session.add(
            Channel(
                youtube_id="UCsync-unresolved",
                resolve_status="pending",
                enabled=True,
                allowed=True,
                blocked=False,
            )
        )
        session.commit()
        session.refresh(allowed_channel)
        allowed_channel_id = allowed_channel.id

        selected = select_sync_channel_ids(session)

    assert selected == [allowed_channel_id]
