from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.core.config import settings
from app.services.youtube import (
    YouTubeResolveError,
    fetch_channel_metadata,
    fetch_latest_videos,
    resolve_channel,
)
from app.services.youtube_ytdlp import fetch_channel_videos, resolve_channel_id

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


@router.get('', response_model=ChannelLookupResponse)
async def channel_lookup(query: str = Query(min_length=1, max_length=500)) -> ChannelLookupResponse:
    normalized = query.strip()
    try:
        if settings.youtube_api_key:
            metadata = await resolve_channel(normalized)
            channel_id = metadata.get('channel_id')
            if not channel_id:
                raise YouTubeResolveError('Unable to resolve the channel from this query.')

            sample = await fetch_latest_videos(channel_id, max_results=6)
        else:
            channel_id = await resolve_channel_id(normalized)
            if not channel_id:
                raise YouTubeResolveError('Unable to resolve channel without API key.')
            metadata = await fetch_channel_metadata(channel_id)
            sample_ydl = await fetch_channel_videos(channel_id, max_results=6)
            sample = [
                {
                    'youtube_id': item.get('video_id'),
                    'title': item.get('title'),
                    'thumbnail_url': item.get('thumbnail_url'),
                    'published_at': item.get('published_at') or '',
                    'duration': str(item.get('duration')) if item.get('duration') is not None else None,
                }
                for item in sample_ydl
                if item.get('video_id')
            ]

        channel = ChannelLookupPreview(
            youtube_id=channel_id,
            title=metadata.get('title'),
            handle=metadata.get('handle'),
            avatar_url=metadata.get('avatar_url'),
            banner_url=metadata.get('banner_url'),
            description=metadata.get('description'),
            subscriber_count=metadata.get('subscriber_count'),
            video_count=metadata.get('video_count'),
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
