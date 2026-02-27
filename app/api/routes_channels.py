from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.db.models import Channel
from app.db.session import get_session
from app.services.sync import store_videos
from app.services.youtube import fetch_latest_videos, resolve_channel

router = APIRouter()


class ChannelCreate(BaseModel):
    input: str
    category: str | None = None


class ChannelUpdate(BaseModel):
    enabled: bool | None = None
    category: str | None = None
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
