from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session

from app.db.session import get_session
from app.services.limits import check_access

router = APIRouter()


class FeedItem(BaseModel):
    channel_id: int
    channel_youtube_id: str | None
    channel_title: str | None
    channel_avatar_url: str | None
    channel_category: str | None
    channel_category_id: int | None = None
    channel_category_name: str | None = None
    video_youtube_id: str
    video_title: str
    video_thumbnail_url: str
    video_published_at: datetime
    video_duration_seconds: int | None = None
    video_is_short: bool = False
    video_view_count: int | None = None


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
    del cursor
    category_id: int | None = None

    if category is not None:
        category_row = session.execute(
            text(
                """
                SELECT id
                FROM categories
                WHERE name = :category
                  AND enabled = 1
                LIMIT 1
                """
            ),
            {"category": category},
        ).first()
        if not category_row:
            return []
        category_id = int(category_row[0])

    now = datetime.now(timezone.utc)  # noqa: UP017
    if kid_id is not None:
        allowed, _reason, _details = check_access(
            session, kid_id=kid_id, category_id=category_id, now=now
        )
        if not allowed:
            return []
    query = text(
        """
        SELECT
            c.id AS channel_id,
            c.youtube_id AS channel_youtube_id,
            c.title AS channel_title,
            c.avatar_url AS channel_avatar_url,
            c.category AS channel_category,
            c.category_id AS channel_category_id,
            cat.name AS channel_category_name,
            v.youtube_id AS video_youtube_id,
            v.title AS video_title,
            v.thumbnail_url AS video_thumbnail_url,
            v.published_at AS video_published_at,
            v.duration_seconds AS video_duration_seconds,
            v.is_short AS video_is_short,
            v.view_count AS video_view_count
        FROM videos v
        JOIN channels c ON c.id = v.channel_id
        LEFT JOIN categories cat ON cat.id = c.category_id
        WHERE c.enabled = 1
          AND c.allowed = 1
          AND c.blocked = 0
          AND (c.category_id IS NULL OR cat.enabled = 1)
          AND (:channel_id IS NULL OR c.id = :channel_id)
          AND (
            :category IS NULL
            OR (
              (c.category_id IS NOT NULL AND cat.name = :category AND cat.enabled = 1)
              OR (c.category_id IS NULL AND c.category = :category)
            )
          )
          AND v.is_short = 0
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
    return [FeedItem.model_validate(row) for row in rows]


@router.get("/latest-per-channel", response_model=list[FeedItem])
def latest_per_channel(
    kid_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[FeedItem]:
    now = datetime.now(timezone.utc)  # noqa: UP017
    if kid_id is not None:
        allowed, _reason, _details = check_access(
            session, kid_id=kid_id, now=now
        )
        if not allowed:
            return []
    query = text(
        """
        SELECT
            c.id AS channel_id,
            c.youtube_id AS channel_youtube_id,
            c.title AS channel_title,
            c.avatar_url AS channel_avatar_url,
            c.category AS channel_category,
            c.category_id AS channel_category_id,
            cat.name AS channel_category_name,
            v.youtube_id AS video_youtube_id,
            v.title AS video_title,
            v.thumbnail_url AS video_thumbnail_url,
            v.published_at AS video_published_at,
            v.duration_seconds AS video_duration_seconds,
            v.is_short AS video_is_short,
            v.view_count AS video_view_count
        FROM channels c
        JOIN videos v ON v.channel_id = c.id
        LEFT JOIN categories cat ON cat.id = c.category_id
        WHERE c.enabled = 1
          AND c.allowed = 1
          AND c.blocked = 0
          AND (c.category_id IS NULL OR cat.enabled = 1)
          AND v.is_short = 0
          AND v.id = (
            SELECT vv.id
            FROM videos vv
            WHERE vv.channel_id = c.id
              AND vv.is_short = 0
            ORDER BY vv.published_at DESC
            LIMIT 1
          )
        ORDER BY v.published_at DESC
        """
    )
    rows = session.execute(query).mappings().all()
    return [FeedItem.model_validate(row) for row in rows]


@router.get('/shorts', response_model=list[FeedItem])
def list_shorts(
    limit: int = Query(default=20, ge=1, le=50),
    kid_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[FeedItem]:
    now = datetime.now(timezone.utc)  # noqa: UP017
    if kid_id is not None:
        allowed, _reason, _details = check_access(
            session, kid_id=kid_id, now=now
        )
        if not allowed:
            return []
    rows = session.execute(
        text(
            """
            SELECT
                c.id AS channel_id,
                c.youtube_id AS channel_youtube_id,
                c.title AS channel_title,
                c.avatar_url AS channel_avatar_url,
                c.category AS channel_category,
                c.category_id AS channel_category_id,
                cat.name AS channel_category_name,
                v.youtube_id AS video_youtube_id,
                v.title AS video_title,
                v.thumbnail_url AS video_thumbnail_url,
                v.published_at AS video_published_at,
                v.duration_seconds AS video_duration_seconds,
                v.is_short AS video_is_short,
                v.view_count AS video_view_count
            FROM videos v
            JOIN channels c ON c.id = v.channel_id
            LEFT JOIN categories cat ON cat.id = c.category_id
            WHERE c.enabled = 1 AND c.allowed = 1 AND c.blocked = 0 AND v.is_short = 1
            ORDER BY v.published_at DESC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).mappings().all()
    return [FeedItem.model_validate(row) for row in rows]
