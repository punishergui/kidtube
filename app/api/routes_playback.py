from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlmodel import Session

from app.db.models import WatchLog
from app.db.session import get_session
from app.services.limits import check_access

router = APIRouter()

_LEGACY_REASON_DETAILS = {
    "daily_limit": "Daily watch limit reached",
    "category_limit": "Daily watch limit reached",
    "bedtime": "Within bedtime window",
    "schedule": "Outside allowed schedule",
}


def _detail_for_reason(reason: str) -> str:
    return _LEGACY_REASON_DETAILS.get(reason, reason)


class PlaybackLogPayload(BaseModel):
    kid_id: int
    youtube_id: str
    seconds_watched: int = Field(ge=1)
    started_at: datetime | None = None


class PlaybackHeartbeatPayload(BaseModel):
    kid_id: int
    video_id: str
    seconds_delta: int | None = Field(default=None, ge=1, le=120)
    position_seconds: int | None = Field(default=None, ge=0)
    is_playing: bool = True
    category_id: int | None = None
    started_at: datetime | None = None


@router.post("/log")
def log_playback(
    payload: PlaybackLogPayload,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    video = (
        session.execute(
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
        )
        .mappings()
        .first()
    )
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    now = datetime.now(UTC)  # noqa: UP017
    allowed, reason, _details = check_access(
        session,
        kid_id=payload.kid_id,
        video_id=payload.youtube_id,
        category_id=video["category_id"],
        now=now,
    )
    if not allowed and reason:
        raise HTTPException(status_code=403, detail=_detail_for_reason(reason))

    watch_log = WatchLog(
        kid_id=payload.kid_id,
        video_id=video["video_id"],
        seconds_watched=payload.seconds_watched,
        category_id=video["category_id"],
        started_at=payload.started_at or now,
    )
    session.add(watch_log)
    session.commit()
    return {"ok": True}


@router.post("/watch/log")
def log_watch_heartbeat(
    payload: PlaybackHeartbeatPayload,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    video = (
        session.execute(
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
        )
        .mappings()
        .first()
    )
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    now = datetime.now(UTC)  # noqa: UP017
    allowed, reason, _details = check_access(
        session,
        kid_id=payload.kid_id,
        video_id=payload.video_id,
        category_id=video["category_id"],
        now=now,
    )
    if not allowed and reason:
        raise HTTPException(status_code=403, detail=_detail_for_reason(reason))

    if not payload.is_playing:
        return {"ok": True}

    most_recent = session.execute(
        text(
            """
            SELECT created_at
            FROM watch_log
            WHERE kid_id = :kid_id AND video_id = :video_id
            ORDER BY id DESC
            LIMIT 1
            """
        ),
        {"kid_id": payload.kid_id, "video_id": video["video_id"]},
    ).first()
    if most_recent and most_recent[0]:
        raw_then = most_recent[0]
        if isinstance(raw_then, datetime):
            then = raw_then
        else:
            then = datetime.fromisoformat(str(raw_then).replace("Z", "+00:00"))
        if then.tzinfo is None:
            then = then.replace(tzinfo=UTC)
        else:
            then = then.astimezone(UTC)
        if (now - then).total_seconds() < 8:
            return {"ok": True}

    seconds_delta = payload.seconds_delta if payload.seconds_delta is not None else 10

    watch_log = WatchLog(
        kid_id=payload.kid_id,
        video_id=video["video_id"],
        seconds_watched=seconds_delta,
        category_id=(
            payload.category_id if payload.category_id is not None else video["category_id"]
        ),
        started_at=payload.started_at or now,
    )
    session.add(watch_log)
    session.commit()
    return {"ok": True}
