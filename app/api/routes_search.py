from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session

from app.db.models import Kid, SearchLog
from app.db.session import get_session
from app.services.youtube import search_videos

router = APIRouter()
logger = logging.getLogger(__name__)


class SearchResult(BaseModel):
    video_id: str
    title: str
    channel_id: str | None
    channel_title: str
    thumbnail_url: str
    published_at: str | None
    duration_seconds: int | None = None
    is_short: bool | None = None
    access_status: str


@router.get("", response_model=list[SearchResult])
async def search(
    q: str = Query(min_length=1, max_length=500),
    kid_id: int = Query(..., ge=1),
    session: Session = Depends(get_session),
) -> list[dict[str, object]]:
    normalized = q.strip()
    kid = session.get(Kid, kid_id)
    if not kid:
        raise HTTPException(status_code=404, detail="Kid not found")

    try:
        results = await search_videos(normalized)
    except Exception:
        logger.debug("search_backend=api_failed", exc_info=True)
        return []

    session.add(SearchLog(kid_id=kid_id, query=normalized))
    session.commit()
    payload: list[dict[str, object]] = []
    for item in results:
        video_id = item.get("video_id")
        channel_id = item.get("channel_id")

        channel_row = None
        if channel_id:
            channel_row = session.execute(
                text(
                    """
                    SELECT allowed, blocked, enabled
                    FROM channels
                    WHERE youtube_id = :youtube_id
                    LIMIT 1
                    """
                ),
                {"youtube_id": channel_id},
            ).first()

        channel_allowed = bool(
            channel_row and channel_row[0] and not channel_row[1] and channel_row[2]
        )
        if channel_allowed:
            access_status = "allowed"
        else:
            pending = session.execute(
                text(
                    """
                    SELECT 1
                    FROM requests
                    WHERE kid_id = :kid_id
                      AND status = 'pending'
                      AND youtube_id IN (:video_id, :channel_id)
                    LIMIT 1
                    """
                ),
                {"kid_id": kid_id, "video_id": video_id, "channel_id": channel_id or ""},
            ).first()
            access_status = "pending" if pending else "needs_request"

        payload.append(
            {
                "video_id": video_id,
                "title": item.get("title"),
                "channel_id": channel_id,
                "channel_title": item.get("channel_title"),
                "thumbnail_url": item.get("thumbnail_url"),
                "published_at": item.get("published_at"),
                "duration_seconds": item.get("duration_seconds"),
                "is_short": item.get("is_short"),
                "access_status": access_status,
            }
        )
    return payload


@router.get("/logs")
def search_logs(
    kid_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> list[dict[str, object | None]]:
    rows = (
        session.execute(
            text(
                """
            SELECT sl.id, sl.kid_id, k.name AS kid_name, sl.query, sl.created_at
            FROM search_log sl
            JOIN kids k ON k.id = sl.kid_id
            WHERE (:kid_id IS NULL OR sl.kid_id = :kid_id)
            ORDER BY sl.created_at DESC, sl.id DESC
            LIMIT :limit
            """
            ),
            {"kid_id": kid_id, "limit": limit},
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]
