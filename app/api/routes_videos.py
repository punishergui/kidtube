from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session

from app.db.session import get_session

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
def get_video(youtube_id: str, session: Session = Depends(get_session)) -> VideoRead:
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
        WHERE v.youtube_id = :youtube_id
        LIMIT 1
        """
    )
    row = session.execute(query, {"youtube_id": youtube_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Video not found")
    return VideoRead.model_validate(row)
