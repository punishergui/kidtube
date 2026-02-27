from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import httpx

from app.core.config import settings

YOUTUBE_API_BASE_URL = "https://www.googleapis.com/youtube/v3"
_CHANNEL_ID_PATTERN = re.compile(r"^UC[\w-]{22}$")
_VIDEO_ID_PATTERN = re.compile(r"^[\w-]{11}$")


class YouTubeResolveError(Exception):
    pass


@dataclass
class ParsedChannelInput:
    channel_id: str | None = None
    handle: str | None = None
    video_id: str | None = None


async def resolve_channel(
    input: str, client: httpx.AsyncClient | None = None
) -> dict[str, str | None]:
    normalized = input.strip()
    parsed = parse_channel_input(normalized)

    if parsed.channel_id:
        return await fetch_channel_metadata(parsed.channel_id, client=client)

    api_key = settings.youtube_api_key
    if not api_key:
        raise YouTubeResolveError(
            "YOUTUBE_API_KEY is not configured. Resolution requires a valid API key."
        )

    if parsed.handle:
        channel_id = await resolve_handle_to_channel_id(parsed.handle, api_key, client=client)
        return await fetch_channel_metadata(channel_id, api_key=api_key, client=client)

    if parsed.video_id:
        channel_id = await resolve_video_to_channel_id(parsed.video_id, api_key, client=client)
        return await fetch_channel_metadata(channel_id, api_key=api_key, client=client)

    raise YouTubeResolveError("Unsupported channel input format. Use @handle or a YouTube URL.")


async def fetch_latest_videos(
    channel_id: str,
    max_results: int = 10,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, str]]:
    api_key = settings.youtube_api_key
    if not api_key:
        raise YouTubeResolveError(
            "YOUTUBE_API_KEY is not configured. Video sync requires a valid API key."
        )

    content_details = await _youtube_get(
        "/channels",
        {
            "part": "contentDetails",
            "id": channel_id,
            "key": api_key,
        },
        client=client,
    )
    items = content_details.get("items", [])
    if not items:
        raise YouTubeResolveError(f"No channel found for id '{channel_id}'.")

    uploads_playlist = items[0].get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
    if not uploads_playlist:
        return []

    payload = await _youtube_get(
        "/playlistItems",
        {
            "part": "snippet",
            "playlistId": uploads_playlist,
            "maxResults": max(1, min(max_results, 50)),
            "key": api_key,
        },
        client=client,
    )

    records: list[dict[str, str]] = []
    for item in payload.get("items", []):
        snippet = item.get("snippet", {})
        resource = snippet.get("resourceId", {})
        video_id = resource.get("videoId")
        if not video_id or not _VIDEO_ID_PATTERN.match(video_id):
            continue

        thumbnails = snippet.get("thumbnails", {})
        thumb = (
            thumbnails.get("high") or thumbnails.get("medium") or thumbnails.get("default") or {}
        )
        published_at = snippet.get("publishedAt")
        if not published_at:
            continue
        records.append(
            {
                "youtube_id": video_id,
                "title": snippet.get("title") or "Untitled",
                "thumbnail_url": thumb.get("url") or "",
                "published_at": published_at,
            }
        )

    return records


def parse_channel_input(input: str) -> ParsedChannelInput:
    value = input.strip()
    if _CHANNEL_ID_PATTERN.match(value):
        return ParsedChannelInput(channel_id=value)
    if value.startswith("@") and len(value) > 1:
        return ParsedChannelInput(handle=value.removeprefix("@"))

    parsed = urlparse(value)
    if parsed.scheme and parsed.netloc:
        host = parsed.netloc.lower()
        path = parsed.path.strip("/")
        if "youtube.com" in host:
            segments = path.split("/") if path else []
            if (
                len(segments) >= 2
                and segments[0] == "channel"
                and _CHANNEL_ID_PATTERN.match(segments[1])
            ):
                return ParsedChannelInput(channel_id=segments[1])
            if segments and segments[0].startswith("@"):
                return ParsedChannelInput(handle=segments[0].removeprefix("@"))
            if segments and segments[0] == "watch":
                video_id = parse_qs(parsed.query).get("v", [None])[0]
                if video_id:
                    return ParsedChannelInput(video_id=video_id)
            if len(segments) >= 2 and segments[0] == "shorts":
                return ParsedChannelInput(video_id=segments[1])
        if host in {"youtu.be", "www.youtu.be"}:
            video_id = path.split("/")[0]
            if video_id:
                return ParsedChannelInput(video_id=video_id)

    return ParsedChannelInput()


async def resolve_handle_to_channel_id(
    handle: str,
    api_key: str,
    client: httpx.AsyncClient | None = None,
) -> str:
    payload = await _youtube_get(
        "/channels",
        {
            "part": "id",
            "forHandle": handle,
            "key": api_key,
        },
        client=client,
    )
    items = payload.get("items", [])
    if not items:
        raise YouTubeResolveError(f"Unable to resolve handle '@{handle}'.")
    channel_id = items[0].get("id")
    if not channel_id:
        raise YouTubeResolveError(f"YouTube response for '@{handle}' did not include a channel id.")
    return channel_id


async def resolve_video_to_channel_id(
    video_id: str,
    api_key: str,
    client: httpx.AsyncClient | None = None,
) -> str:
    payload = await _youtube_get(
        "/videos",
        {
            "part": "snippet",
            "id": video_id,
            "key": api_key,
        },
        client=client,
    )
    items = payload.get("items", [])
    if not items:
        raise YouTubeResolveError(f"Unable to resolve video '{video_id}'.")
    channel_id = items[0].get("snippet", {}).get("channelId")
    if not channel_id:
        raise YouTubeResolveError(f"Video '{video_id}' is missing channel metadata.")
    return channel_id


async def fetch_channel_metadata(
    channel_id: str,
    api_key: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict[str, str | None]:
    if not _CHANNEL_ID_PATTERN.match(channel_id):
        raise YouTubeResolveError(f"Invalid channel id '{channel_id}'.")

    effective_key = api_key or settings.youtube_api_key
    if not effective_key:
        return {
            "channel_id": channel_id,
            "title": None,
            "avatar_url": None,
            "banner_url": None,
        }

    payload = await _youtube_get(
        "/channels",
        {
            "part": "snippet,brandingSettings",
            "id": channel_id,
            "key": effective_key,
        },
        client=client,
    )
    items = payload.get("items", [])
    if not items:
        raise YouTubeResolveError(f"No channel found for id '{channel_id}'.")

    item = items[0]
    snippet = item.get("snippet", {})
    thumbnails = snippet.get("thumbnails", {})
    avatar = thumbnails.get("high") or thumbnails.get("medium") or thumbnails.get("default") or {}
    branding = item.get("brandingSettings", {}).get("image", {})

    return {
        "channel_id": item.get("id", channel_id),
        "title": snippet.get("title"),
        "avatar_url": avatar.get("url"),
        "banner_url": branding.get("bannerExternalUrl"),
    }


async def _youtube_get(
    path: str,
    params: dict[str, str | int],
    client: httpx.AsyncClient | None = None,
) -> dict:
    timeout = httpx.Timeout(settings.http_timeout_seconds)
    if client:
        response = await client.get(f"{YOUTUBE_API_BASE_URL}{path}", params=params)
        response.raise_for_status()
        return response.json()

    async with httpx.AsyncClient(timeout=timeout) as local_client:
        response = await local_client.get(f"{YOUTUBE_API_BASE_URL}{path}", params=params)
        response.raise_for_status()
        return response.json()


def utcnow() -> datetime:
    return datetime.now(UTC)
