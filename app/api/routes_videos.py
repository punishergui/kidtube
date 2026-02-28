from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session

from app.db.models import Kid
from app.db.session import get_session
from app.services.parent_controls import can_watch_now

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
    session: Session = Depends(get_session),
    kid_id: int | None = Query(default=None),
) -> VideoRead:
    if kid_id is not None:
        kid = session.get(Kid, kid_id)
        if not kid:
            raise HTTPException(status_code=404, detail='Kid not found')

        can_watch, reason = can_watch_now(session, kid)
        if not can_watch:
            raise HTTPException(status_code=403, detail=reason or 'Watch not allowed')

        if kid.require_parent_approval:
            approved_row = session.execute(
                text(
                    """
                    SELECT 1
                    FROM requests
                    WHERE type = 'video'
                      AND kid_id = :kid_id
                      AND youtube_id = :youtube_id
                      AND status = 'approved'
                    LIMIT 1
                    """
                ),
                {'kid_id': kid.id, 'youtube_id': youtube_id},
            ).first()
            if not approved_row:
                raise HTTPException(
                    status_code=403,
                    detail='Parent approval required for this video',
                )

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
    row = session.execute(query, {'youtube_id': youtube_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail='Video not found')
    return VideoRead.model_validate(row)
