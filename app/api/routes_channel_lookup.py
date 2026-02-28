from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.youtube import (
    fetch_latest_videos,
    resolve_channel,
)

router = APIRouter()


class ChannelLookupPreview(BaseModel):
    youtube_id: str
    title: str | None
    handle: str | None
    avatar_url: str | None
    banner_url: str | None
    description: str | None
    subscriber_count: int | None
    video_count: int | None


class ChannelLookupVideo(BaseModel):
    youtube_id: str
    title: str
    thumbnail_url: str
    published_at: str
    duration: str | None = None


class ChannelLookupResponse(BaseModel):
    query: str
    found: bool
    channel: ChannelLookupPreview | None
    sample_videos: list[ChannelLookupVideo]
    error: str | None


@router.get("", response_model=ChannelLookupResponse)
async def channel_lookup(query: str = Query(min_length=1, max_length=500)) -> ChannelLookupResponse:
    normalized = query.strip()
    try:
        metadata = await resolve_channel(normalized)
        if not metadata:
            return ChannelLookupResponse(
                query=normalized,
                found=False,
                channel=None,
                sample_videos=[],
                error=None,
            )

        channel_id = metadata.get("channel_id")
        if not channel_id:
            return ChannelLookupResponse(
                query=normalized,
                found=False,
                channel=None,
                sample_videos=[],
                error=None,
            )

        sample = await fetch_latest_videos(channel_id, max_results=6)

        channel = ChannelLookupPreview(
            youtube_id=channel_id,
            title=metadata.get("title"),
            handle=metadata.get("handle"),
            avatar_url=metadata.get("avatar_url"),
            banner_url=metadata.get("banner_url"),
            description=metadata.get("description"),
            subscriber_count=metadata.get("subscriber_count"),
            video_count=metadata.get("video_count"),
        )
        sample_videos = [ChannelLookupVideo(**item) for item in sample]
        return ChannelLookupResponse(
            query=normalized,
            found=True,
            channel=channel,
            sample_videos=sample_videos,
            error=None,
        )
    except Exception as exc:
        return ChannelLookupResponse(
            query=normalized,
            found=False,
            channel=None,
            sample_videos=[],
            error=str(exc),
        )
