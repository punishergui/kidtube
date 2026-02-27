from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlmodel import Session, select

from app.core.config import settings
from app.db.models import Channel, Video
from app.db.session import engine
from app.services.youtube import fetch_channel_metadata, fetch_latest_videos


def select_sync_channel_ids(session: Session) -> list[int]:
    return session.exec(
        select(Channel.id).where(
            Channel.enabled.is_(True),
            Channel.allowed.is_(True),
            Channel.blocked.is_(False),
            Channel.resolve_status == "ok",
        )
    ).all()


async def refresh_channel(channel_id: int) -> None:
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
            videos = await fetch_latest_videos(
                channel.youtube_id,
                max_results=settings.sync_max_videos_per_channel,
            )
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
        channel.resolved_at = datetime.now(UTC)
        channel.last_sync = datetime.now(UTC)
        session.add(channel)

        store_videos(session, channel.id, videos)
        session.commit()


async def refresh_enabled_channels() -> None:
    with Session(engine) as session:
        channels = select_sync_channel_ids(session)

    for channel_id in channels:
        await refresh_channel(channel_id)


def store_videos(session: Session, channel_db_id: int | None, videos: list[dict[str, str]]) -> None:
    if channel_db_id is None:
        return

    for item in videos:
        existing = session.exec(select(Video).where(Video.youtube_id == item["youtube_id"])).first()
        if existing:
            continue

        published_at = datetime.fromisoformat(item["published_at"].replace("Z", "+00:00"))
        session.add(
            Video(
                youtube_id=item["youtube_id"],
                channel_id=channel_db_id,
                title=item["title"],
                thumbnail_url=item["thumbnail_url"],
                published_at=published_at,
            )
        )


async def periodic_sync(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await refresh_enabled_channels()
        except Exception:
            pass
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=settings.sync_interval_seconds)
        except TimeoutError:
            continue
