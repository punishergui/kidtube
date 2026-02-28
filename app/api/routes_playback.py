from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlmodel import Session

from app.db.models import WatchLog
from app.db.session import get_session
from app.services.limits import assert_schedule_allowed, assert_under_limit

router = APIRouter()


class PlaybackLogPayload(BaseModel):
    kid_id: int
    youtube_id: str
    seconds_watched: int = Field(ge=1)
    started_at: datetime | None = None


class PlaybackHeartbeatPayload(BaseModel):
    kid_id: int
    video_id: str
    seconds_delta: int = Field(ge=1, le=120)


@router.post("/log")
def log_playback(
    payload: PlaybackLogPayload,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    video = session.execute(
        text(
            """
            SELECT v.id AS video_id, c.category_id AS category_id
            FROM videos v
            JOIN channels c ON c.id = v.channel_id
            WHERE v.youtube_id = :youtube_id
            LIMIT 1
            """
        ),
        {"youtube_id": payload.youtube_id},
    ).mappings().first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")


    now = datetime.now(timezone.utc)  # noqa: UP017
    assert_schedule_allowed(session, kid_id=payload.kid_id, now=now)
    assert_under_limit(
        session,
        kid_id=payload.kid_id,
        category_id=video["category_id"],
        now=now,
    )

    started_at = payload.started_at or now
    watch_log = WatchLog(
        kid_id=payload.kid_id,
        video_id=video["video_id"],
        seconds_watched=payload.seconds_watched,
        category_id=video["category_id"],
        started_at=started_at,
    )
    session.add(watch_log)
    session.commit()
    return {"ok": True}


@router.post("/watch/log")
def log_watch_heartbeat(
    payload: PlaybackHeartbeatPayload,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    video = session.execute(
        text(
            """
            SELECT v.id AS video_id, c.category_id AS category_id
            FROM videos v
            JOIN channels c ON c.id = v.channel_id
            WHERE v.youtube_id = :youtube_id
            LIMIT 1
            """
        ),
        {"youtube_id": payload.video_id},
    ).mappings().first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    now = datetime.now(timezone.utc)  # noqa: UP017
    assert_schedule_allowed(session, kid_id=payload.kid_id, now=now)
    assert_under_limit(
        session,
        kid_id=payload.kid_id,
        category_id=video["category_id"],
        now=now,
    )

    watch_log = WatchLog(
        kid_id=payload.kid_id,
        video_id=video["video_id"],
        seconds_watched=payload.seconds_delta,
        category_id=video["category_id"],
        started_at=now,
    )
    session.add(watch_log)
    session.commit()
    return {"ok": True}
