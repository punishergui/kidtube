from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session

from app.api.routes_discord import build_approval_embed_payload
from app.core.config import settings
from app.db.models import Request
from app.db.session import get_session

router = APIRouter()
logger = logging.getLogger(__name__)


class RequestCreate(BaseModel):
    youtube_id: str
    kid_id: int | None = None


class RequestRead(BaseModel):
    id: int
    type: str
    youtube_id: str | None
    kid_id: int | None
    status: str


async def _send_discord_request_notification(request_row: Request, session: Session) -> None:
    if not settings.discord_approval_webhook_url:
        return

    kid_name = "Unknown kid"
    if request_row.kid_id:
        kid_row = session.execute(
            text("SELECT name FROM kids WHERE id = :kid_id"),
            {"kid_id": request_row.kid_id},
        ).first()
        if kid_row and kid_row[0]:
            kid_name = str(kid_row[0])

    video_title = None
    channel_name = None
    if request_row.youtube_id:
        video_row = session.execute(
            text(
                """
                SELECT v.title, c.title
                FROM videos v
                LEFT JOIN channels c ON c.id = v.channel_id
                WHERE v.youtube_id = :youtube_id
                LIMIT 1
                """
            ),
            {"youtube_id": request_row.youtube_id},
        ).first()
        if video_row:
            video_title = video_row[0]
            channel_name = video_row[1]

    payload = build_approval_embed_payload(
        request_id=request_row.id,
        request_type=request_row.type,
        youtube_id=request_row.youtube_id,
        kid_name=kid_name,
        video_title=video_title,
        channel_name=channel_name,
    )

    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            response = await client.post(settings.discord_approval_webhook_url, json=payload)
            response.raise_for_status()
    except Exception:
        logger.exception("discord_webhook_send_failed", extra={"request_id": request_row.id})


@router.post("/channel-allow", response_model=RequestRead, status_code=status.HTTP_201_CREATED)
async def create_channel_allow_request(
    payload: RequestCreate,
    session: Session = Depends(get_session),
) -> Request:
    request_row = Request(type="channel", youtube_id=payload.youtube_id, kid_id=payload.kid_id)
    session.add(request_row)
    session.commit()
    session.refresh(request_row)
    await _send_discord_request_notification(request_row, session)
    return request_row


@router.post("/video-allow", response_model=RequestRead, status_code=status.HTTP_201_CREATED)
async def create_video_allow_request(
    payload: RequestCreate,
    session: Session = Depends(get_session),
) -> Request:
    request_row = Request(type="video", youtube_id=payload.youtube_id, kid_id=payload.kid_id)
    session.add(request_row)
    session.commit()
    session.refresh(request_row)
    await _send_discord_request_notification(request_row, session)
    return request_row
