from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlmodel import Session

from app.db.models import SearchLog
from app.db.session import get_session

router = APIRouter()


class SearchLogCreatePayload(BaseModel):
    kid_id: int
    query: str = Field(min_length=1, max_length=500)


@router.post('/search', status_code=201)
def create_search_log(
    payload: SearchLogCreatePayload,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    entry = SearchLog(kid_id=payload.kid_id, query=payload.query.strip())
    session.add(entry)
    session.commit()
    return {'ok': True}


@router.get('/search')
def list_search_logs(
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
        {'kid_id': kid_id, 'limit': limit},
    ).mappings().all()
    return [dict(row) for row in rows]


@router.get('/watch')
def list_watch_logs(
    kid_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> list[dict[str, object | None]]:
    rows = session.execute(
        text(
            """
            SELECT
                wl.id,
                wl.kid_id,
                k.name AS kid_name,
                wl.video_id,
                wl.seconds_watched,
                wl.created_at,
                wl.category_id,
                v.youtube_id AS video_youtube_id,
                v.title AS video_title
            FROM watch_log wl
            JOIN kids k ON k.id = wl.kid_id
            LEFT JOIN videos v ON v.id = wl.video_id
            WHERE (:kid_id IS NULL OR wl.kid_id = :kid_id)
            ORDER BY wl.created_at DESC, wl.id DESC
            LIMIT :limit
            """
        ),
        {'kid_id': kid_id, 'limit': limit},
    ).mappings().all()
    return [dict(row) for row in rows]


@router.get('/recent')
def list_recent_watch_logs(
    kid_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> list[dict[str, object | None]]:
    rows = session.execute(
        text(
            """
            SELECT
                wl.id,
                wl.kid_id,
                k.name AS kid_name,
                wl.seconds_watched,
                wl.created_at,
                v.title AS video_title,
                c.title AS channel_title,
                cat.name AS category_name
            FROM watch_log wl
            JOIN kids k ON k.id = wl.kid_id
            LEFT JOIN videos v ON v.id = wl.video_id
            LEFT JOIN channels c ON c.id = v.channel_id
            LEFT JOIN categories cat ON cat.id = wl.category_id
            WHERE (:kid_id IS NULL OR wl.kid_id = :kid_id)
            ORDER BY wl.created_at DESC, wl.id DESC
            LIMIT :limit
            """
        ),
        {'kid_id': kid_id, 'limit': limit},
    ).mappings().all()
    return [dict(row) for row in rows]
