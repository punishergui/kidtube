from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import text
from sqlmodel import Session

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_daily_stats(session: Session) -> None:
    if not settings.discord_approval_webhook_url:
        logger.debug("daily_stats_skipped_no_webhook")
        return

    now = datetime.now(timezone.utc)  # noqa: UP017
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    kids = session.execute(
        text("SELECT id, name FROM kids ORDER BY created_at, id")
    ).mappings().all()

    embeds: list[dict[str, object]] = []
    for kid in kids:
        kid_id = int(kid["id"])
        kid_name = str(kid["name"])

        watch = session.execute(
            text(
                """
                SELECT COALESCE(SUM(wl.seconds_watched), 0) AS watched_seconds
                FROM watch_log wl
                WHERE wl.kid_id = :kid_id
                  AND wl.created_at >= :today_start
                """
            ),
            {"kid_id": kid_id, "today_start": today_start},
        ).mappings().first()
        watched_minutes = round((int(watch["watched_seconds"]) if watch else 0) / 60, 1)

        top_videos = session.execute(
            text(
                """
                SELECT
                    COALESCE(v.title, 'Unknown video') AS title,
                    COALESCE(SUM(wl.seconds_watched), 0) AS watched_seconds
                FROM watch_log wl
                LEFT JOIN videos v ON v.id = wl.video_id
                WHERE wl.kid_id = :kid_id
                  AND wl.created_at >= :today_start
                GROUP BY v.id, v.title
                ORDER BY watched_seconds DESC
                LIMIT 3
                """
            ),
            {"kid_id": kid_id, "today_start": today_start},
        ).mappings().all()

        searches = session.execute(
            text(
                """
                SELECT query
                FROM search_log
                WHERE kid_id = :kid_id
                  AND created_at >= :today_start
                ORDER BY created_at DESC
                LIMIT 5
                """
            ),
            {"kid_id": kid_id, "today_start": today_start},
        ).mappings().all()

        top_videos_text = "\n".join(
            f"• {row['title']} ({round(int(row['watched_seconds']) / 60, 1)} min)"
            for row in top_videos
        ) or "No videos watched today"

        searches_text = "\n".join(f"• {row['query']}" for row in searches) or "No searches today"

        embeds.append(
            {
                "title": f"Daily Stats · {kid_name}",
                "color": 0x5F6DFF,
                "fields": [
                    {
                        "name": "Total watch time",
                        "value": f"{watched_minutes} minutes",
                        "inline": True,
                    },
                    {"name": "Top videos", "value": top_videos_text, "inline": False},
                    {"name": "Searches", "value": searches_text, "inline": False},
                ],
            }
        )

    payload: dict[str, object] = {
        "content": "KidTube daily stats report",
        "embeds": embeds or [{"title": "Daily Stats", "description": "No kids configured."}],
        "footer": {"text": f"{today_start.date().isoformat()} · Powered by KidTube"},
    }

    for embed in payload.get("embeds", []):
        if isinstance(embed, dict):
            embed["footer"] = {"text": f"{today_start.date().isoformat()} · Powered by KidTube"}

    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            response = await client.post(settings.discord_approval_webhook_url, json=payload)
            response.raise_for_status()
    except Exception:
        logger.exception("daily_stats_send_failed")
