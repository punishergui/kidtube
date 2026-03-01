from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlmodel import Session, select

from app.core.config import settings
from app.db.models import Channel, Video
from app.db.session import engine
from app.services.youtube import (
    YouTubeResolveError,
    fetch_channel_metadata,
    fetch_latest_videos,
    fetch_videos_before,
    resolve_channel,
)
from app.services.youtube_ytdlp import fetch_channel_videos

logger = logging.getLogger(__name__)


def select_sync_channel_ids(session: Session) -> list[int]:
    return session.exec(
        select(Channel.id).where(
            Channel.enabled.is_(True),
            Channel.allowed.is_(True),
            Channel.blocked.is_(False),
            Channel.resolve_status == "ok",
        )
    ).all()


def select_eligible_channels(session: Session) -> list[Channel]:
    return session.exec(
        select(Channel).where(
            Channel.enabled.is_(True),
            Channel.allowed.is_(True),
            Channel.blocked.is_(False),
        )
    ).all()


async def _fetch_channel_videos_with_fallback(
    channel_youtube_id: str,
) -> list[dict[str, str | int | bool | None]]:
    if settings.youtube_api_key:
        try:
            api_videos = await fetch_latest_videos(
                channel_youtube_id,
                max_results=settings.sync_max_videos_per_channel,
            )
            logger.debug("sync_backend=api")
            return api_videos
        except Exception:
            logger.debug("sync_backend=api_failed_fallback_to_ytdlp", exc_info=True)

    ytdlp_videos = await fetch_channel_videos(
        channel_youtube_id,
        max_results=settings.sync_max_videos_per_channel,
    )
    logger.debug("sync_backend=ytdlp")
    records = [
        {
            "youtube_id": str(item.get("video_id") or ""),
            "title": str(item.get("title") or "Untitled"),
            "thumbnail_url": str(item.get("thumbnail_url") or ""),
            "published_at": str(item.get("published_at") or datetime.now(timezone.utc).isoformat()),  # noqa: UP017
            "duration_seconds": item.get("duration_seconds"),
            "is_short": bool(item.get("is_short", False)),
            "view_count": item.get("view_count"),
        }
        for item in ytdlp_videos
        if item.get("video_id")
    ]
    return records


async def sync_channel_deep(session: Session, channel: Channel) -> int:
    if not settings.deep_sync_enabled:
        return 0

    oldest_row = session.execute(
        text("SELECT MIN(published_at) FROM videos WHERE channel_id = :channel_id"),
        {"channel_id": channel.id},
    ).first()
    oldest_published_at = oldest_row[0] if oldest_row else None

    if oldest_published_at is None:
        videos = await _fetch_channel_videos_with_fallback(channel.youtube_id)
    else:
        videos = await fetch_videos_before(
            channel.youtube_id,
            published_before=oldest_published_at.isoformat(),
            max_results=settings.sync_max_videos_per_channel,
        )

    if not videos:
        return 0
    return store_videos(session, channel.id, videos)


async def refresh_enabled_channels_deep() -> dict[str, int | list[dict[str, str | int | None]]]:
    summary: dict[str, int | list[dict[str, str | int | None]]] = {
        "channels_seen": 0,
        "resolved": 0,
        "synced": 0,
        "failed": 0,
        "failures": [],
    }

    with Session(engine) as session:
        channels = select_eligible_channels(session)
        for channel in channels:
            summary["channels_seen"] = int(summary["channels_seen"]) + 1
            try:
                added = await sync_channel_deep(session, channel)
                channel.last_sync = datetime.now(timezone.utc)  # noqa: UP017
                if added > 0:
                    summary["synced"] = int(summary["synced"]) + 1
            except Exception as exc:
                channel.resolve_error = str(exc)
                summary["failed"] = int(summary["failed"]) + 1
                failures = summary["failures"]
                assert isinstance(failures, list)
                failures.append({"id": channel.id, "input": channel.input, "error": str(exc)})
            finally:
                session.add(channel)
        session.commit()

    return summary


async def refresh_channel(channel_id: int) -> int:
    with Session(engine) as session:
        channel = session.get(Channel, channel_id)
        if (
            not channel
            or channel.resolve_status != "ok"
            or not channel.enabled
            or not channel.allowed
            or channel.blocked
        ):
            return

        try:
            metadata = await fetch_channel_metadata(channel.youtube_id)
            videos = await _fetch_channel_videos_with_fallback(channel.youtube_id)
            if not videos:
                raise RuntimeError("No videos returned from API or yt-dlp fallback")
        except Exception as exc:
            channel.resolve_error = str(exc)
            session.add(channel)
            session.commit()
            return

        channel.title = metadata.get("title")
        channel.avatar_url = metadata.get("avatar_url")
        channel.banner_url = metadata.get("banner_url")
        channel.resolve_status = "ok"
        channel.resolve_error = None
        channel.resolved_at = datetime.now(timezone.utc)  # noqa: UP017
        channel.last_sync = datetime.now(timezone.utc)  # noqa: UP017
        session.add(channel)

        store_videos(session, channel.id, videos)
        session.commit()


async def refresh_enabled_channels() -> dict[str, int | list[dict[str, str | int | None]]]:
    summary: dict[str, int | list[dict[str, str | int | None]]] = {
        "channels_seen": 0,
        "resolved": 0,
        "synced": 0,
        "failed": 0,
        "failures": [],
    }

    with Session(engine) as session:
        channels = select_eligible_channels(session)

        for channel in channels:
            summary["channels_seen"] = int(summary["channels_seen"]) + 1
            try:
                if channel.resolve_status != "ok":
                    source_input = channel.input or channel.youtube_id
                    metadata = await resolve_channel(source_input)
                    channel.youtube_id = metadata["channel_id"] or channel.youtube_id
                    channel.title = metadata.get("title")
                    channel.avatar_url = metadata.get("avatar_url")
                    channel.banner_url = metadata.get("banner_url")
                    channel.resolve_status = "ok"
                    channel.resolve_error = None
                    channel.resolved_at = datetime.now(timezone.utc)  # noqa: UP017
                    summary["resolved"] = int(summary["resolved"]) + 1

                metadata = await fetch_channel_metadata(channel.youtube_id)
                videos = await _fetch_channel_videos_with_fallback(channel.youtube_id)
                if not videos:
                    raise RuntimeError("No videos returned from API or yt-dlp fallback")
                channel.title = metadata.get("title")
                channel.avatar_url = metadata.get("avatar_url")
                channel.banner_url = metadata.get("banner_url")
                channel.resolve_status = "ok"
                channel.resolve_error = None
                channel.last_sync = datetime.now(timezone.utc)  # noqa: UP017
                store_videos(session, channel.id, videos)
                summary["synced"] = int(summary["synced"]) + 1
            except Exception as exc:
                if isinstance(exc, YouTubeResolveError):
                    channel.resolve_status = "failed"
                channel.resolve_error = str(exc)
                summary["failed"] = int(summary["failed"]) + 1
                failures = summary["failures"]
                assert isinstance(failures, list)
                failures.append(
                    {
                        "id": channel.id,
                        "input": channel.input,
                        "error": str(exc),
                    }
                )
                logger.error(
                    "channel_sync_failed",
                    extra={"channel_id": channel.id, "error": str(exc)},
                )
            finally:
                session.add(channel)

        session.commit()

    return summary


def store_videos(
    session: Session, channel_db_id: int | None, videos: list[dict[str, str | int | bool | None]]
) -> None:
    if channel_db_id is None:
        return 0

    shorts_marked = 0
    added_count = 0
    for item in videos:
        existing = session.exec(select(Video).where(Video.youtube_id == item["youtube_id"])).first()
        duration_seconds = item.get("duration_seconds")
        normalized_duration = int(duration_seconds) if isinstance(duration_seconds, int) else None
        is_short = bool(item.get("is_short", False))

        if existing:
            should_update = existing.duration_seconds is None or not bool(existing.is_short)
            if should_update:
                was_short = bool(existing.is_short)
                existing.duration_seconds = normalized_duration
                existing.is_short = is_short
                session.add(existing)
                if is_short and not was_short:
                    shorts_marked += 1
            incoming_view_count = item.get("view_count")
            if isinstance(incoming_view_count, int):
                existing.view_count = incoming_view_count or existing.view_count
                session.add(existing)
            continue

        published_at = datetime.fromisoformat(item["published_at"].replace("Z", "+00:00"))
        if is_short:
            shorts_marked += 1
        session.add(
            Video(
                youtube_id=str(item["youtube_id"]),
                channel_id=channel_db_id,
                title=str(item["title"]),
                thumbnail_url=str(item["thumbnail_url"]),
                published_at=published_at,
                duration_seconds=normalized_duration,
                is_short=is_short,
                view_count=(
                    item.get("view_count")
                    if isinstance(item.get("view_count"), int)
                    else None
                ),
            )
        )
        added_count += 1

    logger.info(
        "sync_shorts_marked",
        extra={"channel_db_id": channel_db_id, "shorts_marked": shorts_marked},
    )
    return added_count


async def periodic_sync(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            summary = await refresh_enabled_channels()
            logger.info("Periodic sync completed", extra={"sync_summary": summary})
        except Exception as exc:
            logger.warning("Periodic sync failed: %s", exc)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=settings.sync_interval_seconds)
        except TimeoutError:
            continue
