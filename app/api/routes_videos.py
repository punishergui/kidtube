from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session, select

from app.db.models import Video
from app.db.session import get_session
from app.services.parent_controls import assert_playback_allowed

router = APIRouter()


class VideoRead(BaseModel):
    youtube_id: str
    title: str
    thumbnail_url: str
    published_at: datetime
    channel_id: int
    channel_title: str | None
    channel_avatar_url: str | None


@router.get("/{youtube_id}", response_model=VideoRead)
def get_video(youtube_id: str, request: Request, session: Session = Depends(get_session)) -> VideoRead:
    query = text(
        """
        SELECT
            v.youtube_id,
            v.title,
            v.thumbnail_url,
            v.published_at,
            c.id AS channel_id,
            c.title AS channel_title,
            c.avatar_url AS channel_avatar_url
        FROM videos v
        JOIN channels c ON c.id = v.channel_id
        LEFT JOIN categories cat ON cat.id = c.category_id
        WHERE v.youtube_id = :youtube_id
          AND c.enabled = 1
          AND c.allowed = 1
          AND c.blocked = 0
          AND COALESCE(cat.enabled, 1) = 1
        LIMIT 1
        """
    )
    row = session.execute(query, {"youtube_id": youtube_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Video not found")

    kid_id = request.session.get('kid_id')
    if not kid_id:
        raise HTTPException(status_code=403, detail='Kid session is required')

    video = session.exec(select(Video).where(Video.youtube_id == youtube_id)).first()
    if not video:
        raise HTTPException(status_code=404, detail='Video not found')
    assert_playback_allowed(session, kid_id, video)
    return VideoRead.model_validate(row)
