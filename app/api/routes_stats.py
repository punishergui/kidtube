from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session

from app.db.session import get_session

router = APIRouter()


class ShortsTogglePayload(BaseModel):
    enabled: bool


@router.get('/stats')
def watch_stats(
    kid_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    now = datetime.now(timezone.utc)  # noqa: UP017
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    by_category = session.execute(
        text(
            """
            SELECT
                wl.kid_id AS kid_id,
                k.name AS kid_name,
                wl.category_id AS category_id,
                cat.name AS category_name,
                COALESCE(SUM(wl.seconds_watched), 0) AS lifetime_seconds,
                COALESCE(SUM(
                    CASE
                        WHEN wl.created_at >= :today_start THEN wl.seconds_watched
                        ELSE 0
                    END
                ), 0) AS today_seconds
            FROM watch_log wl
            JOIN kids k ON k.id = wl.kid_id
            LEFT JOIN categories cat ON cat.id = wl.category_id
            WHERE (:kid_id IS NULL OR wl.kid_id = :kid_id)
            GROUP BY wl.kid_id, k.name, wl.category_id, cat.name
            ORDER BY lifetime_seconds DESC
            """
        ),
        {'kid_id': kid_id, 'today_start': today_start},
    ).mappings().all()

    totals = session.execute(
        text(
            """
            SELECT
                MAX(k.name) AS kid_name,
                COALESCE(SUM(wl.seconds_watched), 0) AS lifetime_seconds,
                COALESCE(SUM(
                    CASE
                        WHEN wl.created_at >= :today_start THEN wl.seconds_watched
                        ELSE 0
                    END
                ), 0) AS today_seconds
            FROM watch_log wl
            JOIN kids k ON k.id = wl.kid_id
            WHERE (:kid_id IS NULL OR wl.kid_id = :kid_id)
            """
        ),
        {'kid_id': kid_id, 'today_start': today_start},
    ).mappings().first()

    return {
        'kid_id': kid_id,
        'kid_name': totals['kid_name'] if totals else None,
        'today_seconds': int(totals['today_seconds']) if totals else 0,
        'lifetime_seconds': int(totals['lifetime_seconds']) if totals else 0,
        'categories': [
            {
                'kid_id': row['kid_id'],
                'kid_name': row['kid_name'],
                'category_id': row['category_id'],
                'category_name': row['category_name'],
                'today_seconds': int(row['today_seconds']),
                'lifetime_seconds': int(row['lifetime_seconds']),
            }
            for row in by_category
        ],
    }


@router.get('/settings/shorts')
def get_shorts_setting(session: Session = Depends(get_session)) -> dict[str, bool]:
    row = session.execute(text("SELECT shorts_enabled FROM parent_settings WHERE id = 1")).first()
    return {'enabled': bool(row[0]) if row else True}


@router.put('/settings/shorts')
def set_shorts_setting(
    payload: ShortsTogglePayload,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    session.execute(
        text(
            "INSERT INTO parent_settings(id, shorts_enabled) VALUES (1, :enabled) "
            "ON CONFLICT(id) DO UPDATE SET shorts_enabled = :enabled"
        ),
        {'enabled': 1 if payload.enabled else 0},
    )
    session.commit()
    return {'enabled': payload.enabled}
