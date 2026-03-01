from __future__ import annotations

import asyncio
import json
import logging
import shutil
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _normalize_record(item: dict[str, object]) -> dict[str, object]:
    video_id = str(item.get("id") or "")
    channel_id = item.get("channel_id")
    if not isinstance(channel_id, str):
        channel_id = None
    duration = item.get("duration")
    duration_seconds = int(duration) if isinstance(duration, (int, float)) else None
    source_url = str(item.get("webpage_url") or item.get("url") or "")

    upload_date = item.get("upload_date")
    published_at = None
    if isinstance(upload_date, str) and len(upload_date) == 8 and upload_date.isdigit():
        try:
            dt = datetime.strptime(upload_date, "%Y%m%d").replace(tzinfo=timezone.utc)  # noqa: UP017
            published_at = dt.isoformat().replace("+00:00", "Z")
        except ValueError:
            published_at = None

    return {
        "video_id": video_id,
        "title": str(item.get("title") or "Untitled"),
        "channel_title": str(item.get("channel") or item.get("uploader") or "Unknown channel"),
        "channel_id": channel_id,
        "thumbnail_url": str(item.get("thumbnail") or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"),
        "duration": duration_seconds,
        "duration_seconds": duration_seconds,
        "is_short": bool(
            (duration_seconds is not None and duration_seconds <= 60)
            or ("/shorts/" in source_url)
        ),
        "published_at": published_at,
    }


async def _run_ytdlp(args: list[str]) -> str:
    if shutil.which("yt-dlp") is None:
        logger.warning("yt_dlp_missing")
        return ""

    try:
        process = await asyncio.create_subprocess_exec(
            "yt-dlp",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except Exception:
        logger.warning("yt_dlp_spawn_failed", exc_info=True)
        return ""

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
    except TimeoutError:
        process.kill()
        await process.communicate()
        logger.warning("yt_dlp_timeout", extra={"args": args})
        return ""

    if process.returncode != 0:
        logger.warning(
            "yt_dlp_failed",
            extra={"args": args, "stderr": stderr.decode(errors="ignore")[:500]},
        )
        return ""

    return stdout.decode(errors="ignore")


async def search_youtube(query: str, max_results: int = 20) -> list[dict]:
    stdout = await _run_ytdlp(
        [f"ytsearch{max_results}:{query}", "--dump-json", "--flat-playlist", "--no-warnings"]
    )
    if not stdout:
        return []

    records: list[dict] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        records.append(_normalize_record(item))

    return records


async def fetch_channel_videos(channel_id: str, max_results: int = 15) -> list[dict]:
    stdout = await _run_ytdlp(
        [
            f"https://www.youtube.com/channel/{channel_id}/videos",
            "--dump-json",
            "--flat-playlist",
            "--playlist-end",
            str(max_results),
            "--no-warnings",
        ]
    )
    if not stdout:
        return []

    records: list[dict] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        records.append(_normalize_record(item))

    return records


async def resolve_channel_id(handle_or_url: str) -> str | None:
    stdout = await _run_ytdlp(
        [
            handle_or_url,
            "--dump-single-json",
            "--flat-playlist",
            "--playlist-end",
            "1",
            "--no-warnings",
        ]
    )
    if not stdout:
        return None

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return None

    channel_id = payload.get("channel_id") or payload.get("uploader_id")
    if isinstance(channel_id, str) and channel_id:
        return channel_id
    return None
