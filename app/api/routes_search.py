from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session

from app.db.models import SearchLog
from app.db.session import get_session
from app.services.limits import is_in_any_schedule, is_in_bedtime
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
    now = datetime.now(timezone.utc)  # noqa: UP017
    if not is_in_any_schedule(session, kid_id=kid_id, now=now) or is_in_bedtime(
        session, kid_id=kid_id, now=now
    ):
        return []

    session.add(SearchLog(kid_id=kid_id, query=normalized))
    session.commit()
    try:
        return await search_videos(normalized)
    except Exception:
        logger.debug("search_backend=api_failed", exc_info=True)
        return []


@router.get("/logs")
def search_logs(
    kid_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> list[dict[str, object | None]]:
    rows = session.execute(
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
    ).mappings().all()
    return [dict(row) for row in rows]
