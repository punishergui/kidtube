from __future__ import annotations

from datetime import datetime, time

from fastapi import HTTPException
from sqlalchemy import text
from sqlmodel import Session, select

from app.db.models import Category, Kid, KidBonusTime, KidCategoryLimit, KidSchedule, Video, WatchLog


def _today_window(now: datetime) -> tuple[datetime, datetime]:
    start = datetime(now.year, now.month, now.day)
    end = datetime(now.year, now.month, now.day, 23, 59, 59)
    return start, end


def _is_in_schedule(session: Session, kid_id: int, now: datetime) -> bool:
    schedules = session.exec(
        select(KidSchedule).where(KidSchedule.kid_id == kid_id, KidSchedule.day_of_week == now.weekday())
    ).all()
    if not schedules:
        return True
    now_time = now.time()
    return any(s.start_time <= now_time <= s.end_time for s in schedules)


def _category_limit_minutes(session: Session, kid: Kid, category_id: int | None) -> int | None:
    if not category_id:
        return kid.daily_limit_minutes

    override = session.exec(
        select(KidCategoryLimit).where(
            KidCategoryLimit.kid_id == kid.id,
            KidCategoryLimit.category_id == category_id,
        )
    ).first()
    if override:
        return override.daily_limit_minutes

    category = session.get(Category, category_id)
    if category and category.daily_limit_minutes is not None:
        return category.daily_limit_minutes
    return kid.daily_limit_minutes


def _bonus_minutes(session: Session, kid_id: int, now: datetime) -> int:
    grants = session.exec(
        select(KidBonusTime).where(KidBonusTime.kid_id == kid_id, KidBonusTime.expires_at >= now)
    ).all()
    return sum(max(0, g.minutes - g.used_minutes) for g in grants)


def assert_playback_allowed(session: Session, kid_id: int, video: Video, now: datetime | None = None) -> None:
    kid = session.get(Kid, kid_id)
    if not kid:
        raise HTTPException(status_code=403, detail="Kid session is required")

    current = now or datetime.utcnow()
    if not _is_in_schedule(session, kid_id, current):
        raise HTTPException(status_code=403, detail="Outside allowed schedule")

    limit = _category_limit_minutes(session, kid, _video_category_id(session, video.id))
    if limit is None:
        return

    day_start, day_end = _today_window(current)
    watched = session.exec(
        select(WatchLog).where(
            WatchLog.kid_id == kid_id,
            WatchLog.watched_at >= day_start,
            WatchLog.watched_at <= day_end,
        )
    ).all()
    watched_minutes = sum(max(0, row.watched_seconds) for row in watched) // 60
    if watched_minutes >= limit + _bonus_minutes(session, kid_id, current):
        raise HTTPException(status_code=403, detail="Daily limit reached")


def _video_category_id(session: Session, video_id: int) -> int | None:
    row = session.execute(
        text("""
        SELECT c.category_id
        FROM videos v
        JOIN channels c ON c.id = v.channel_id
        WHERE v.id = :video_id
        LIMIT 1
        """
        ),
        {"video_id": video_id},
    ).first()
    if not row:
        return None
    return row[0]
