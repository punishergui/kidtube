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


class FeedItem(BaseModel):
    channel_id: int
    channel_youtube_id: str | None
    channel_title: str | None
    channel_avatar_url: str | None
    channel_category: str | None
    video_youtube_id: str
    video_title: str
    video_thumbnail_url: str
    video_published_at: datetime


@router.get("", response_model=list[FeedItem])
def list_feed(
    session: Session = Depends(get_session),
    limit: int = Query(default=30, ge=1, le=100),
    channel_id: int | None = Query(default=None),
    category: str | None = Query(default=None),
    kid_id: int | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = Query(default=None),
) -> list[FeedItem]:
    kid: Kid | None = None
    del cursor

    if kid_id is not None:
        kid = session.get(Kid, kid_id)
        if not kid:
            raise HTTPException(status_code=404, detail='Kid not found')

        can_watch, _ = can_watch_now(session, kid)
        if not can_watch:
            return []

    query = text(
        """
        SELECT
            c.id AS channel_id,
            c.youtube_id AS channel_youtube_id,
            c.title AS channel_title,
            c.avatar_url AS channel_avatar_url,
            c.category AS channel_category,
            v.youtube_id AS video_youtube_id,
            v.title AS video_title,
            v.thumbnail_url AS video_thumbnail_url,
            v.published_at AS video_published_at
        FROM videos v
        JOIN channels c ON c.id = v.channel_id
        WHERE c.enabled = 1
          AND c.allowed = 1
          AND c.blocked = 0
          AND (:channel_id IS NULL OR c.id = :channel_id)
          AND (:category IS NULL OR c.category = :category)
        ORDER BY v.published_at DESC
        LIMIT :limit OFFSET :offset
        """
    )
    rows = session.execute(
        query,
        {
            "channel_id": channel_id,
            "category": category,
            "limit": limit,
            "offset": offset,
        },
    ).mappings().all()

    items = [FeedItem.model_validate(row) for row in rows]
    if kid and kid.require_parent_approval:
        approved_rows = session.execute(
            text(
                """
                SELECT youtube_id
                FROM requests
                WHERE type = 'video'
                  AND kid_id = :kid_id
                  AND status = 'approved'
                """
            ),
            {'kid_id': kid.id},
        ).all()
        approved_ids = {row[0] for row in approved_rows}
        items = [item for item in items if item.video_youtube_id in approved_ids]

    return items


@router.get("/latest-per-channel", response_model=list[FeedItem])
def latest_per_channel(
    session: Session = Depends(get_session),
    kid_id: int | None = Query(default=None),
) -> list[FeedItem]:
    query = text(
        """
        SELECT
            c.id AS channel_id,
            c.youtube_id AS channel_youtube_id,
            c.title AS channel_title,
            c.avatar_url AS channel_avatar_url,
            c.category AS channel_category,
            v.youtube_id AS video_youtube_id,
            v.title AS video_title,
            v.thumbnail_url AS video_thumbnail_url,
            v.published_at AS video_published_at
        FROM channels c
        JOIN videos v ON v.channel_id = c.id
        WHERE c.enabled = 1
          AND c.allowed = 1
          AND c.blocked = 0
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
    if kid_id is not None:
        kid = session.get(Kid, kid_id)
        if not kid:
            raise HTTPException(status_code=404, detail='Kid not found')

        can_watch, _ = can_watch_now(session, kid)
        if not can_watch:
            return []
    else:
        kid = None

    rows = session.execute(query).mappings().all()
    items = [FeedItem.model_validate(row) for row in rows]

    if kid and kid.require_parent_approval:
        approved_rows = session.execute(
            text(
                """
                SELECT youtube_id
                FROM requests
                WHERE type = 'video'
                  AND kid_id = :kid_id
                  AND status = 'approved'
                """
            ),
            {'kid_id': kid.id},
        ).all()
        approved_ids = {row[0] for row in approved_rows}
        items = [item for item in items if item.video_youtube_id in approved_ids]

    return items
