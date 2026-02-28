from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import text
from sqlmodel import Session


def _utc_day_bounds(now: datetime) -> tuple[datetime, datetime]:
    now_utc = now.astimezone(datetime.UTC) if now.tzinfo else now.replace(tzinfo=datetime.UTC)
    day_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    return day_start, day_end


def _resolve_limit_minutes(session: Session, kid_id: int, category_id: int | None) -> int | None:
    if category_id is not None:
        kid_category_limit = session.execute(
            text(
                """
                SELECT daily_limit_minutes
                FROM kid_category_limits
                WHERE kid_id = :kid_id AND category_id = :category_id
                LIMIT 1
                """
            ),
            {"kid_id": kid_id, "category_id": category_id},
        ).first()
        if kid_category_limit:
            return int(kid_category_limit[0])

    kid_limit = session.execute(
        text(
            """
            SELECT daily_limit_minutes
            FROM kids
            WHERE id = :kid_id
            LIMIT 1
            """
        ),
        {"kid_id": kid_id},
    ).first()
    if not kid_limit:
        raise HTTPException(status_code=404, detail="Kid not found")

    return int(kid_limit[0]) if kid_limit[0] is not None else None


def remaining_seconds_for(
    session: Session,
    kid_id: int,
    category_id: int | None,
    now: datetime,
) -> int | None:
    limit_minutes = _resolve_limit_minutes(session, kid_id, category_id)
    if limit_minutes is None:
        return None

    day_start, day_end = _utc_day_bounds(now)

    watched_seconds = session.execute(
        text(
            """
            SELECT COALESCE(SUM(seconds_watched), 0)
            FROM watch_log
            WHERE kid_id = :kid_id
              AND (
                (:category_id IS NULL AND category_id IS NULL)
                OR category_id = :category_id
              )
              AND started_at >= :day_start
              AND started_at < :day_end
            """
        ),
        {
            "kid_id": kid_id,
            "category_id": category_id,
            "day_start": day_start.isoformat(),
            "day_end": day_end.isoformat(),
        },
    ).one()[0]

    return (limit_minutes * 60) - int(watched_seconds)


def assert_under_limit(
    session: Session,
    kid_id: int,
    category_id: int | None,
    now: datetime,
) -> None:
    remaining_seconds = remaining_seconds_for(session, kid_id, category_id, now)
    if remaining_seconds is not None and remaining_seconds <= 0:
        raise HTTPException(status_code=403, detail="Daily watch limit reached")
