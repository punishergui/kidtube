from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session

from app.api.routes_discord import build_approval_embed_payload
from app.core.config import settings
from app.db.models import Request
from app.db.session import get_session
from app.services.email_notify import send_approval_request_email

router = APIRouter()
logger = logging.getLogger(__name__)
REQUEST_COOLDOWN_SECONDS = 30


class RequestCreate(BaseModel):
    youtube_id: str
    kid_id: int | None = None


class RequestRead(BaseModel):
    id: int
    type: str
    youtube_id: str | None
    kid_id: int | None
    status: str


class RequestQueueRead(BaseModel):
    id: int
    type: str
    channel_id: str | None = None
    channel_url: str | None = None
    video_id: str | None = None
    video_url: str | None = None
    title: str | None = None
    requested_by_kid_id: int | None = None
    requested_by_kid_name: str | None = None
    created_at: datetime
    status: str


async def _send_request_notifications(request_row: Request, session: Session) -> None:
    webhook_url = settings.discord_approval_webhook_url

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

    thumbnail_url = None
    if request_row.youtube_id:
        thumb_row = session.execute(
            text("SELECT thumbnail_url FROM videos WHERE youtube_id = :youtube_id LIMIT 1"),
            {"youtube_id": request_row.youtube_id},
        ).first()
        if thumb_row and thumb_row[0]:
            thumbnail_url = str(thumb_row[0])

    await send_approval_request_email(
        request_id=request_row.id,
        request_type=request_row.type,
        youtube_id=request_row.youtube_id,
        kid_name=kid_name,
        video_title=video_title,
        channel_name=channel_name,
        thumbnail_url=thumbnail_url,
    )

    if not webhook_url:
        logger.info("discord_webhook_not_configured")
        return

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
            response = await client.post(webhook_url, json=payload)
            if response.status_code >= 400:
                logger.error(
                    "discord_webhook_send_failed",
                    extra={
                        "request_id": request_row.id,
                        "webhook_url": webhook_url,
                        "status_code": response.status_code,
                        "response_body": response.text,
                    },
                )
            else:
                logger.info(
                    "discord_webhook_send_ok",
                    extra={
                        "request_id": request_row.id,
                        "webhook_url": webhook_url,
                        "status_code": response.status_code,
                    },
                )
    except httpx.HTTPError as exc:
        logger.error(
            "discord_webhook_send_failed",
            extra={"request_id": request_row.id, "webhook_url": webhook_url, "error": str(exc)},
        )


def _cooldown_retry_after_seconds(session: Session, kid_id: int | None) -> int | None:
    if kid_id is None:
        return None

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=REQUEST_COOLDOWN_SECONDS)  # noqa: UP017
    latest_row = session.execute(
        text(
            """
            SELECT created_at
            FROM requests
            WHERE kid_id = :kid_id
              AND created_at >= :cutoff
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """
        ),
        {"kid_id": kid_id, "cutoff": cutoff.isoformat()},
    ).first()
    if not latest_row:
        return None

    created_at = latest_row[0]
    if not isinstance(created_at, datetime):
        try:
            created_at = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
        except ValueError:
            return REQUEST_COOLDOWN_SECONDS
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=datetime.UTC)

    elapsed = (datetime.now(timezone.utc) - created_at).total_seconds()  # noqa: UP017
    retry_after = REQUEST_COOLDOWN_SECONDS - int(elapsed)
    return retry_after if retry_after > 0 else None


def _apply_request_action(session: Session, request_row: Request, action: str) -> Request:
    now = datetime.now(timezone.utc)  # noqa: UP017
    if action == "deny":
        if request_row.status == "denied":
            return request_row
        request_row.status = "denied"
        request_row.resolved_at = now
        session.add(request_row)
        session.commit()
        session.refresh(request_row)
        return request_row

    if action != "approve":
        return request_row

    if request_row.status == "approved":
        return request_row

    request_row.status = "approved"
    request_row.resolved_at = now

    if request_row.type == "channel" and request_row.youtube_id:
        session.execute(
            text(
                """
                INSERT INTO channels(youtube_id, allowed, enabled, blocked, resolve_status)
                VALUES (:youtube_id, 1, 1, 0, 'pending')
                ON CONFLICT(youtube_id) DO UPDATE SET allowed = 1, blocked = 0, enabled = 1
                """
            ),
            {"youtube_id": request_row.youtube_id},
        )
    elif request_row.type == "video" and request_row.youtube_id:
        existing = session.execute(
            text("SELECT id FROM video_approvals WHERE youtube_id = :youtube_id LIMIT 1"),
            {"youtube_id": request_row.youtube_id},
        ).first()
        if not existing:
            session.execute(
                text(
                    """
                    INSERT INTO video_approvals(youtube_id, request_id)
                    VALUES (:youtube_id, :request_id)
                    """
                ),
                {"youtube_id": request_row.youtube_id, "request_id": request_row.id},
            )

    session.add(request_row)
    session.commit()
    session.refresh(request_row)
    return request_row


@router.post("/channel-allow", response_model=RequestRead, status_code=status.HTTP_201_CREATED)
async def create_channel_allow_request(
    payload: RequestCreate,
    session: Session = Depends(get_session),
) -> Request | JSONResponse:
    retry_after = _cooldown_retry_after_seconds(session, payload.kid_id)
    if retry_after:
        return JSONResponse(
            status_code=429,
            content={"detail": "cooldown", "retry_after": retry_after},
            headers={"Retry-After": str(retry_after)},
        )

    request_row = Request(type="channel", youtube_id=payload.youtube_id, kid_id=payload.kid_id)
    session.add(request_row)
    session.commit()
    session.refresh(request_row)
    await _send_request_notifications(request_row, session)
    return request_row


@router.post("/video-allow", response_model=RequestRead, status_code=status.HTTP_201_CREATED)
async def create_video_allow_request(
    payload: RequestCreate,
    session: Session = Depends(get_session),
) -> Request | JSONResponse:
    retry_after = _cooldown_retry_after_seconds(session, payload.kid_id)
    if retry_after:
        return JSONResponse(
            status_code=429,
            content={"detail": "cooldown", "retry_after": retry_after},
            headers={"Retry-After": str(retry_after)},
        )

    request_row = Request(type="video", youtube_id=payload.youtube_id, kid_id=payload.kid_id)
    session.add(request_row)
    session.commit()
    session.refresh(request_row)
    await _send_request_notifications(request_row, session)
    return request_row


@router.get("", response_model=list[RequestQueueRead])
def list_requests(
    status_filter: str = Query(default="pending", alias="status"),
    session: Session = Depends(get_session),
) -> list[dict[str, object | None]]:
    if status_filter not in {"pending", "approved", "denied"}:
        raise HTTPException(status_code=400, detail="invalid_status")

    rows = (
        session.execute(
            text(
                """
            SELECT
                r.id,
                r.type,
                r.youtube_id,
                r.created_at,
                r.status,
                r.kid_id AS requested_by_kid_id,
                k.name AS requested_by_kid_name,
                v.title AS video_title,
                c.title AS channel_title,
                vv.youtube_id AS video_channel_id
            FROM requests r
            LEFT JOIN kids k ON k.id = r.kid_id
            LEFT JOIN videos v ON v.youtube_id = r.youtube_id
            LEFT JOIN channels c ON c.youtube_id = r.youtube_id
            LEFT JOIN videos vv ON vv.youtube_id = r.youtube_id
            WHERE r.status = :status
            ORDER BY r.created_at DESC, r.id DESC
            """
            ),
            {"status": status_filter},
        )
        .mappings()
        .all()
    )

    payload: list[dict[str, object | None]] = []
    for row in rows:
        youtube_id = row["youtube_id"]
        request_type = row["type"]
        channel_id = str(youtube_id) if request_type == "channel" and youtube_id else None
        video_id = str(youtube_id) if request_type == "video" and youtube_id else None
        payload.append(
            {
                "id": row["id"],
                "type": request_type,
                "channel_id": channel_id,
                "channel_url": (
                    f"https://www.youtube.com/channel/{channel_id}" if channel_id else None
                ),
                "video_id": video_id,
                "video_url": (f"https://www.youtube.com/watch?v={video_id}" if video_id else None),
                "title": row["video_title"] or row["channel_title"],
                "requested_by_kid_id": row["requested_by_kid_id"],
                "requested_by_kid_name": row["requested_by_kid_name"],
                "created_at": row["created_at"],
                "status": row["status"],
            }
        )
    return payload


@router.post("/{request_id}/approve", response_model=RequestRead)
def approve_request(request_id: int, session: Session = Depends(get_session)) -> Request:
    request_row = session.get(Request, request_id)
    if not request_row:
        raise HTTPException(status_code=404, detail="request_not_found")
    return _apply_request_action(session, request_row, "approve")


@router.post("/{request_id}/deny", response_model=RequestRead)
def deny_request(request_id: int, session: Session = Depends(get_session)) -> Request:
    request_row = session.get(Request, request_id)
    if not request_row:
        raise HTTPException(status_code=404, detail="request_not_found")
    return _apply_request_action(session, request_row, "deny")
