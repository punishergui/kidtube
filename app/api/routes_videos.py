from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session

from app.db.session import get_session
from app.services.limits import assert_under_limit

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
            c.title AS channel_title,
            c.avatar_url AS channel_avatar_url,
            c.category_id AS category_id
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
        assert_under_limit(
            session,
            kid_id=kid_id,
            category_id=row["category_id"],
            now=datetime.now(datetime.UTC),
        )

    return VideoRead.model_validate(row)
