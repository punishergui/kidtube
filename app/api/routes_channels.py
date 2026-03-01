from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.db.models import Channel
from app.db.session import get_session
from app.services.limits import check_access
from app.services.sync import store_videos
from app.services.youtube import fetch_latest_videos, resolve_channel

router = APIRouter()


class ChannelCreate(BaseModel):
    input: str
    category: str | None = None
    category_id: int | None = None


class ChannelUpdate(BaseModel):
    enabled: bool | None = None
    category: str | None = None
    category_id: int | None = None
    allowed: bool | None = None
    blocked: bool | None = None
    blocked_reason: str | None = None


class ChannelRead(BaseModel):
    id: int
    youtube_id: str
    input: str | None
    title: str | None
    avatar_url: str | None
    banner_url: str | None
    category: str | None
    category_id: int | None
    allowed: bool
    blocked: bool
    blocked_reason: str | None
    enabled: bool
    last_sync: datetime | None
    resolved_at: datetime | None
    resolve_status: str
    resolve_error: str | None
    created_at: datetime


@router.get("", response_model=list[ChannelRead])
def list_channels(session: Session = Depends(get_session)) -> list[Channel]:
    return session.exec(select(Channel).order_by(Channel.id)).all()


@router.post("", response_model=ChannelRead, status_code=status.HTTP_201_CREATED)
async def create_channel(
    payload: ChannelCreate,
    session: Session = Depends(get_session),
) -> Channel:
    raw_input = payload.input.strip()
    placeholder_id = f"pending:{uuid4()}"
    channel = Channel(
        youtube_id=placeholder_id,
        input=raw_input,
        category=payload.category,
        category_id=payload.category_id,
        resolve_status="pending",
    )

    try:
        metadata = await resolve_channel(raw_input)
        channel.youtube_id = metadata["channel_id"] or placeholder_id
        channel.title = metadata.get("title")
        channel.avatar_url = metadata.get("avatar_url")
        channel.banner_url = metadata.get("banner_url")
        channel.resolve_status = "ok"
        channel.resolve_error = None
        channel.resolved_at = datetime.now(timezone.utc)  # noqa: UP017
    except Exception as exc:
        channel.resolve_status = "failed"
        channel.resolve_error = str(exc)

    session.add(channel)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Channel already exists") from exc

    session.refresh(channel)

    if channel.resolve_status == "ok" and channel.allowed and not channel.blocked:
        try:
            videos = await fetch_latest_videos(channel.youtube_id)
            store_videos(session, channel.id, videos)
            channel.last_sync = datetime.now(timezone.utc)  # noqa: UP017
            session.add(channel)
            session.commit()
            session.refresh(channel)
        except Exception as exc:
            channel.resolve_error = str(exc)
            session.add(channel)
            session.commit()
            session.refresh(channel)

    return channel


@router.patch("/{channel_id}", response_model=ChannelRead)
def patch_channel(
    channel_id: int,
    payload: ChannelUpdate,
    session: Session = Depends(get_session),
) -> Channel:
    channel = session.get(Channel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    data = payload.model_dump(exclude_unset=True)
    blocked_before = channel.blocked

    for field, value in data.items():
        setattr(channel, field, value)

    if channel.blocked and not blocked_before:
        channel.blocked_at = datetime.now(timezone.utc)  # noqa: UP017
        session.execute(
            text("DELETE FROM videos WHERE channel_id = :channel_id"),
            {"channel_id": channel.id},
        )

    session.add(channel)
    session.commit()
    session.refresh(channel)
    return channel


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_channel(channel_id: int, session: Session = Depends(get_session)) -> Response:
    channel = session.get(Channel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    session.execute(
        text("DELETE FROM videos WHERE channel_id = :channel_id"),
        {"channel_id": channel_id},
    )
    session.delete(channel)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get('/allowed')
def list_allowed_channels(
    kid_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[dict[str, object | None]]:
    rows = session.execute(
        text(
            """
            SELECT id, youtube_id, title, avatar_url, banner_url, category, category_id
            FROM channels
            WHERE enabled = 1 AND allowed = 1 AND blocked = 0
            ORDER BY COALESCE(title, youtube_id)
            """
        )
    ).mappings().all()
    return [dict(row) for row in rows]




@router.get('/youtube/{channel_youtube_id}')
def channel_detail(
    channel_youtube_id: str,
    kid_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
) -> dict[str, object | None]:
    row = session.execute(
        text(
            """
            SELECT id, youtube_id, title, avatar_url, banner_url, category, category_id, input
            FROM channels
            WHERE youtube_id = :channel_youtube_id
              AND enabled = 1
              AND allowed = 1
              AND blocked = 0
            LIMIT 1
            """
        ),
        {"channel_youtube_id": channel_youtube_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Channel not found")
    if kid_id is not None:
        allowed, reason, _details = check_access(
            session,
            kid_id=kid_id,
            channel_id=channel_youtube_id,
            now=datetime.now(timezone.utc),  # noqa: UP017
        )
        if not allowed and reason:
            raise HTTPException(status_code=403, detail=reason)
    return dict(row)
@router.get('/{channel_youtube_id}/videos')
def channel_videos(
    channel_youtube_id: str,
    kid_id: int | None = Query(default=None),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> list[dict[str, object | None]]:
    rows = session.execute(
        text(
            """
            SELECT
                v.youtube_id AS video_youtube_id,
                v.title AS video_title,
                v.thumbnail_url AS video_thumbnail_url,
                v.published_at AS video_published_at,
                v.duration_seconds AS video_duration_seconds,
                v.view_count AS video_view_count
            FROM videos v
            JOIN channels c ON c.id = v.channel_id
            WHERE c.youtube_id = :channel_youtube_id
              AND c.enabled = 1
              AND c.allowed = 1
              AND c.blocked = 0
            ORDER BY v.published_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"channel_youtube_id": channel_youtube_id, "limit": limit, "offset": offset},
    ).mappings().all()
    return [dict(row) for row in rows]
