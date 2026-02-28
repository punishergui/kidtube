from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import text
from sqlmodel import Session


def _utc_day_bounds(now: datetime) -> tuple[datetime, datetime]:
    now_utc = now.astimezone(timezone.utc) if now.tzinfo else now.replace(  # noqa: UP017
        tzinfo=timezone.utc  # noqa: UP017
    )
    day_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    return day_start, day_end


def _time_to_minutes(value: str) -> int:
    hours_str, minutes_str = value.split(":", 1)
    hours = int(hours_str)
    minutes = int(minutes_str)
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        raise ValueError("Invalid time value")
    return (hours * 60) + minutes


def _is_within_window(now_minutes: int, start_minutes: int, end_minutes: int) -> bool:
    if start_minutes <= end_minutes:
        return start_minutes <= now_minutes <= end_minutes
    return now_minutes >= start_minutes or now_minutes <= end_minutes


def is_in_any_schedule(session: Session, kid_id: int, now: datetime) -> bool:
    rows = session.execute(
        text(
            """
            SELECT start_time, end_time
            FROM kid_schedules
            WHERE kid_id = :kid_id
              AND day_of_week = :day_of_week
            """
        ),
        {
            "kid_id": kid_id,
            "day_of_week": now.weekday(),
        },
    ).all()

    if not rows:
        return True

    now_minutes = (now.hour * 60) + now.minute
    for start_time, end_time in rows:
        try:
            start_minutes = _time_to_minutes(start_time)
            end_minutes = _time_to_minutes(end_time)
        except ValueError:
            continue

        if _is_within_window(now_minutes, start_minutes, end_minutes):
            return True

    return False


def is_in_bedtime(session: Session, kid_id: int, now: datetime) -> bool:
    bedtime = session.execute(
        text(
            """
            SELECT bedtime_start, bedtime_end
            FROM kids
            WHERE id = :kid_id
            LIMIT 1
            """
        ),
        {"kid_id": kid_id},
    ).first()
    if not bedtime:
        raise HTTPException(status_code=404, detail="Kid not found")

    bedtime_start, bedtime_end = bedtime
    if bedtime_start is None or bedtime_end is None:
        return False

    try:
        start_minutes = _time_to_minutes(str(bedtime_start))
        end_minutes = _time_to_minutes(str(bedtime_end))
    except ValueError:
        return False

    now_minutes = (now.hour * 60) + now.minute
    return _is_within_window(now_minutes, start_minutes, end_minutes)


def assert_schedule_allowed(session: Session, kid_id: int, now: datetime) -> None:
    if not is_in_any_schedule(session, kid_id, now):
        raise HTTPException(status_code=403, detail="Outside allowed schedule")
    if is_in_bedtime(session, kid_id, now):
        raise HTTPException(status_code=403, detail="Within bedtime window")


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


def active_bonus_seconds(session: Session, kid_id: int, now: datetime) -> int:
    active_bonus_minutes = session.execute(
        text(
            """
            SELECT COALESCE(SUM(minutes), 0)
            FROM kid_bonus_time
            WHERE kid_id = :kid_id
              AND (expires_at IS NULL OR expires_at > :now)
            """
        ),
        {
            "kid_id": kid_id,
            "now": now.isoformat(),
        },
    ).one()[0]
    return int(active_bonus_minutes) * 60


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

    return ((limit_minutes * 60) + active_bonus_seconds(session, kid_id, now)) - int(
        watched_seconds
    )


def assert_under_limit(
    session: Session,
    kid_id: int,
    category_id: int | None,
    now: datetime,
) -> None:
    remaining_seconds = remaining_seconds_for(session, kid_id, category_id, now)
    if remaining_seconds is not None and remaining_seconds <= 0:
        raise HTTPException(status_code=403, detail="Daily watch limit reached")
