from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlmodel import Session

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


async def _send_discord_request_notification(request_row: Request) -> None:
    if not settings.discord_approval_webhook_url:
        return

    content = (
        f"Approval request #{request_row.id}: {request_row.type}"
        f" youtube_id={request_row.youtube_id or '-'} kid_id={request_row.kid_id or '-'}"
    )
    payload = {
        "content": content,
        "components": [
            {
                "type": 1,
                "components": [
                    {
                        "type": 2,
                        "style": 3,
                        "label": "Approve",
                        "custom_id": f"request:{request_row.id}:approve",
                    },
                    {
                        "type": 2,
                        "style": 4,
                        "label": "Deny",
                        "custom_id": f"request:{request_row.id}:deny",
                    },
                ],
            }
        ],
    }

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
    await _send_discord_request_notification(request_row)
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
    await _send_discord_request_notification(request_row)
    return request_row
