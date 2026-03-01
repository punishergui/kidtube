from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import text
from sqlmodel import Session

ACCESS_REASON_DAILY_LIMIT = "daily_limit"
ACCESS_REASON_CATEGORY_LIMIT = "category_limit"
ACCESS_REASON_SCHEDULE = "schedule"
ACCESS_REASON_BEDTIME = "bedtime"
ACCESS_REASON_PENDING_APPROVAL = "pending_approval"
ACCESS_REASON_BLOCKED_CHANNEL = "blocked_channel"
ACCESS_REASON_WORD_FILTER = "word_filter"
ACCESS_REASON_SHORTS_DISABLED = "shorts_disabled"


def _utc_day_bounds(now: datetime) -> tuple[datetime, datetime]:
    now_utc = (
        now.astimezone(timezone.utc)  # noqa: UP017
        if now.tzinfo
        else now.replace(  # noqa: UP017
            tzinfo=timezone.utc  # noqa: UP017
        )
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
    day_of_week_py = now.weekday()
    day_of_week_sun_first = (day_of_week_py + 1) % 7
    rows = session.execute(
        text(
            """
            SELECT start_time, end_time
            FROM kid_schedules
            WHERE kid_id = :kid_id
              AND day_of_week IN (:day_of_week_py, :day_of_week_sun_first)
            """
        ),
        {
            "kid_id": kid_id,
            "day_of_week_py": day_of_week_py,
            "day_of_week_sun_first": day_of_week_sun_first,
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


def _parent_blocked_words(session: Session) -> list[str]:
    row = session.execute(text("SELECT blocked_words FROM parent_settings WHERE id = 1")).first()
    if not row or not row[0]:
        return []
    raw = str(row[0]).strip()
    if not raw:
        return []
    return [word.strip().lower() for word in raw.split(",") if word.strip()]


def check_access(
    session: Session,
    kid_id: int,
    *,
    video_id: str | None = None,
    channel_id: str | None = None,
    category_id: int | None = None,
    is_shorts: bool = False,
    title: str | None = None,
    now: datetime | None = None,
) -> tuple[bool, str | None, dict[str, object]]:
    now = now or datetime.now(timezone.utc)  # noqa: UP017

    if not is_in_any_schedule(session, kid_id=kid_id, now=now):
        return False, ACCESS_REASON_SCHEDULE, {}
    if is_in_bedtime(session, kid_id=kid_id, now=now):
        return False, ACCESS_REASON_BEDTIME, {}

    resolved = None
    if video_id:
        resolved = (
            session.execute(
                text(
                    """
                SELECT
                    v.title AS video_title,
                    v.is_short AS video_is_short,
                    c.youtube_id AS channel_youtube_id,
                    c.category_id AS category_id,
                    c.allowed AS channel_allowed,
                    c.blocked AS channel_blocked
                FROM videos v
                JOIN channels c ON c.id = v.channel_id
                WHERE v.youtube_id = :video_id
                LIMIT 1
                """
                ),
                {"video_id": video_id},
            )
            .mappings()
            .first()
        )
        if resolved:
            if category_id is None:
                category_id = resolved["category_id"]
            if not channel_id:
                channel_id = resolved["channel_youtube_id"]
            if not title:
                title = resolved["video_title"]
            is_shorts = bool(resolved["video_is_short"])

    remaining_seconds = remaining_seconds_for(
        session,
        kid_id=kid_id,
        category_id=category_id,
        now=now,
    )
    if remaining_seconds is not None and remaining_seconds <= 0:
        category_limit_exists = False
        if category_id is not None:
            category_limit_exists = (
                session.execute(
                    text(
                        """
                        SELECT 1 FROM kid_category_limits
                        WHERE kid_id = :kid_id AND category_id = :category_id
                        LIMIT 1
                        """
                    ),
                    {"kid_id": kid_id, "category_id": category_id},
                ).first()
                is not None
            )
        return (
            False,
            ACCESS_REASON_CATEGORY_LIMIT if category_limit_exists else ACCESS_REASON_DAILY_LIMIT,
            {"remaining_seconds": int(remaining_seconds)},
        )

    if is_shorts:
        shorts_enabled = session.execute(
            text("SELECT shorts_enabled FROM parent_settings WHERE id = 1")
        ).first()
        if shorts_enabled and int(shorts_enabled[0]) == 0:
            return False, ACCESS_REASON_SHORTS_DISABLED, {}

    if channel_id:
        channel_row = session.execute(
            text(
                """
                SELECT allowed, blocked
                FROM channels
                WHERE youtube_id = :channel_id
                LIMIT 1
                """
            ),
            {"channel_id": channel_id},
        ).first()
        if channel_row and int(channel_row[1]) == 1:
            return False, ACCESS_REASON_BLOCKED_CHANNEL, {}

    lowered_title = (title or "").lower()
    for blocked_word in _parent_blocked_words(session):
        if blocked_word and blocked_word in lowered_title:
            return False, ACCESS_REASON_WORD_FILTER, {"word": blocked_word}

    if video_id:
        channel_allowed = bool(resolved["channel_allowed"]) if resolved else False
        video_approved = (
            session.execute(
                text("SELECT 1 FROM video_approvals WHERE youtube_id = :youtube_id LIMIT 1"),
                {"youtube_id": video_id},
            ).first()
            is not None
        )
        if not channel_allowed and not video_approved:
            request_row = session.execute(
                text(
                    """
                    SELECT status
                    FROM requests
                    WHERE kid_id = :kid_id
                      AND (
                        (type = 'video' AND youtube_id = :video_id)
                        OR (type = 'channel' AND youtube_id = :channel_id)
                      )
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                    """
                ),
                {"kid_id": kid_id, "video_id": video_id, "channel_id": channel_id},
            ).first()
            request_status = str(request_row[0]) if request_row else "none"
            return False, ACCESS_REASON_PENDING_APPROVAL, {"request_status": request_status}

    return True, None, {}
