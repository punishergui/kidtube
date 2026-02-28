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


@router.get('/stats/daily-summary')
def daily_summary(session: Session = Depends(get_session)) -> list[dict[str, object]]:
    now = datetime.now(timezone.utc)  # noqa: UP017
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    kid_rows = session.execute(text("SELECT id, name FROM kids ORDER BY id")).mappings().all()
    if not kid_rows:
        return []

    split_rows = session.execute(
        text(
            """
            SELECT
                wl.kid_id,
                COALESCE(SUM(wl.seconds_watched), 0) AS total_seconds,
                COALESCE(
                    SUM(
                        CASE
                            WHEN lower(COALESCE(cat.name, '')) = 'education' THEN wl.seconds_watched
                            ELSE 0
                        END
                    ),
                    0
                ) AS education_seconds,
                COALESCE(
                    SUM(
                        CASE
                            WHEN lower(COALESCE(cat.name, '')) = 'fun' THEN wl.seconds_watched
                            ELSE 0
                        END
                    ),
                    0
                ) AS fun_seconds
            FROM watch_log wl
            LEFT JOIN categories cat ON cat.id = wl.category_id
            WHERE wl.created_at >= :today_start
            GROUP BY wl.kid_id
            """
        ),
        {'today_start': today_start},
    ).mappings().all()
    split_by_kid = {int(row['kid_id']): row for row in split_rows}

    top_rows = session.execute(
        text(
            """
            SELECT
                ranked.kid_id,
                ranked.channel_title,
                ranked.minutes
            FROM (
                SELECT
                    wl.kid_id,
                    COALESCE(c.title, 'Unknown channel') AS channel_title,
                    CAST(ROUND(COALESCE(SUM(wl.seconds_watched), 0) / 60.0) AS INTEGER) AS minutes,
                    ROW_NUMBER() OVER (
                        PARTITION BY wl.kid_id
                        ORDER BY
                            COALESCE(SUM(wl.seconds_watched), 0) DESC,
                            COALESCE(c.title, 'Unknown channel')
                    ) AS rank_n
                FROM watch_log wl
                LEFT JOIN videos v ON v.id = wl.video_id
                LEFT JOIN channels c ON c.id = v.channel_id
                WHERE wl.created_at >= :today_start
                GROUP BY wl.kid_id, COALESCE(c.title, 'Unknown channel')
            ) ranked
            WHERE ranked.rank_n <= 3
            ORDER BY ranked.kid_id, ranked.rank_n
            """
        ),
        {'today_start': today_start},
    ).mappings().all()
    top_by_kid: dict[int, list[dict[str, object]]] = {}
    for row in top_rows:
        kid_id = int(row['kid_id'])
        top_by_kid.setdefault(kid_id, []).append(
            {'title': row['channel_title'], 'minutes': int(row['minutes'] or 0)}
        )

    denied_rows = session.execute(
        text(
            """
            SELECT kid_id, COUNT(*) AS denied_count
            FROM requests
            WHERE status = 'denied'
              AND created_at >= :today_start
              AND kid_id IS NOT NULL
            GROUP BY kid_id
            """
        ),
        {'today_start': today_start},
    ).mappings().all()
    denied_by_kid = {int(row['kid_id']): int(row['denied_count']) for row in denied_rows}

    search_rows = session.execute(
        text(
            """
            SELECT kid_id, COUNT(*) AS searches_count
            FROM search_log
            WHERE created_at >= :today_start
            GROUP BY kid_id
            """
        ),
        {'today_start': today_start},
    ).mappings().all()
    search_by_kid = {int(row['kid_id']): int(row['searches_count']) for row in search_rows}

    payload: list[dict[str, object]] = []
    for kid in kid_rows:
        kid_id = int(kid['id'])
        split = split_by_kid.get(kid_id)
        total_seconds = int(split['total_seconds']) if split else 0
        education_seconds = int(split['education_seconds']) if split else 0
        fun_seconds = int(split['fun_seconds']) if split else 0
        payload.append(
            {
                'kid_id': kid_id,
                'kid_name': kid['name'],
                'total_minutes_today': round(total_seconds / 60, 1),
                'education_minutes_today': round(education_seconds / 60, 1),
                'fun_minutes_today': round(fun_seconds / 60, 1),
                'top_channels': top_by_kid.get(kid_id, []),
                'denied_requests_today': denied_by_kid.get(kid_id, 0),
                'searches_today': search_by_kid.get(kid_id, 0),
            }
        )

    return payload


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
