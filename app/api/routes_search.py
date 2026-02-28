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
    return [
        {
            "video_id": item.get("video_id"),
            "title": item.get("title"),
            "channel_id": item.get("channel_id"),
            "channel_title": item.get("channel_title"),
            "thumbnail_url": item.get("thumbnail_url"),
            "published_at": item.get("published_at"),
            "duration_seconds": item.get("duration_seconds"),
            "is_short": item.get("is_short"),
        }
        for item in results
    ]


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
