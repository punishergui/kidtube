from __future__ import annotations

from datetime import datetime, time

from sqlalchemy import text
from sqlmodel import Session

from app.db.models import Kid


def _parse_clock(value: str) -> time | None:
    try:
        return datetime.strptime(value, '%H:%M').time()
    except ValueError:
        return None


def is_in_bedtime_window(kid: Kid, now: datetime | None = None) -> bool:
    if not kid.bedtime_start or not kid.bedtime_end:
        return False

    start = _parse_clock(kid.bedtime_start)
    end = _parse_clock(kid.bedtime_end)
    if not start or not end:
        return False

    current = (now or datetime.utcnow()).time()
    if start <= end:
        return start <= current < end
    return current >= start or current < end


def daily_allowance_minutes(kid: Kid, now: datetime | None = None) -> int | None:
    base = kid.daily_limit_minutes
    if base is None:
        return None

    current = now or datetime.utcnow()
    if current.weekday() >= 5 and kid.weekend_bonus_minutes:
        return base + kid.weekend_bonus_minutes
    return base


def watched_today_seconds(session: Session, kid_id: int) -> int:
    row = session.execute(
        text(
            """
            SELECT COALESCE(SUM(watched_seconds), 0) AS total
            FROM watch_log
            WHERE kid_id = :kid_id
              AND DATE(watched_at) = DATE('now')
            """
        ),
        {'kid_id': kid_id},
    ).one()
    return int(row[0] or 0)


def can_watch_now(
    session: Session,
    kid: Kid,
    now: datetime | None = None,
) -> tuple[bool, str | None]:
    if is_in_bedtime_window(kid, now=now):
        return False, 'Bedtime is active for this profile.'

    allowance = daily_allowance_minutes(kid, now=now)
    if allowance is None:
        return True, None

    watched = watched_today_seconds(session, kid.id)
    if watched >= allowance * 60:
        return False, 'Daily watch limit reached for this profile.'

    return True, None
