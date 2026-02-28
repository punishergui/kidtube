from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session

from app.db.session import get_session
from app.services.limits import check_access

router = APIRouter()

_LEGACY_REASON_DETAILS = {
    "daily_limit": "Daily watch limit reached",
    "category_limit": "Daily watch limit reached",
    "bedtime": "Within bedtime window",
    "schedule": "Outside allowed schedule",
}


def _legacy_detail_for_reason(reason: str) -> str:
    return _LEGACY_REASON_DETAILS.get(reason, reason)


class VideoRead(BaseModel):
    youtube_id: str
    title: str
    thumbnail_url: str
    published_at: datetime
    channel_id: int
    channel_title: str | None
    channel_avatar_url: str | None


@router.get("/{youtube_id}", response_model=VideoRead)
def get_video(
    youtube_id: str,
    kid_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
) -> VideoRead:
    query = text(
        """
        SELECT
            v.youtube_id,
            v.title,
            v.thumbnail_url,
            v.published_at,
            c.id AS channel_id,
            c.youtube_id AS channel_youtube_id,
            c.title AS channel_title,
            c.avatar_url AS channel_avatar_url,
            c.category_id AS category_id,
            c.allowed AS channel_allowed,
            c.blocked AS channel_blocked
        FROM videos v
        JOIN channels c ON c.id = v.channel_id
        WHERE v.youtube_id = :youtube_id
        LIMIT 1
        """
    )
    row = session.execute(query, {"youtube_id": youtube_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Video not found")

    if kid_id is not None:
        allowed, reason, _details = check_access(
            session,
            kid_id=kid_id,
            video_id=youtube_id,
            channel_id=row["channel_youtube_id"] if "channel_youtube_id" in row else None,
            category_id=row["category_id"],
            title=row["title"],
            now=datetime.now(timezone.utc),  # noqa: UP017
        )
        if not allowed and reason:
            raise HTTPException(status_code=403, detail=_legacy_detail_for_reason(reason))

    return VideoRead.model_validate(row)
