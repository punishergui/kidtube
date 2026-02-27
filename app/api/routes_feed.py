from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session

from app.db.session import get_session

router = APIRouter(prefix="/api/feed", tags=["feed"])


class FeedItem(BaseModel):
    channel_id: int
    channel_title: str | None
    channel_avatar_url: str | None
    video_youtube_id: str
    video_title: str
    video_thumbnail_url: str
    video_published_at: datetime


@router.get("/latest-per-channel", response_model=list[FeedItem])
def latest_per_channel(session: Session = Depends(get_session)) -> list[FeedItem]:
    query = text(
        """
        SELECT
            c.id AS channel_id,
            c.title AS channel_title,
            c.avatar_url AS channel_avatar_url,
            v.youtube_id AS video_youtube_id,
            v.title AS video_title,
            v.thumbnail_url AS video_thumbnail_url,
            v.published_at AS video_published_at
        FROM channels c
        JOIN videos v ON v.channel_id = c.id
        WHERE c.enabled = 1
          AND v.id = (
            SELECT vv.id
            FROM videos vv
            WHERE vv.channel_id = c.id
            ORDER BY vv.published_at DESC
            LIMIT 1
          )
        ORDER BY v.published_at DESC
        """
    )
    rows = session.exec(query).mappings().all()
    return [FeedItem.model_validate(row) for row in rows]
