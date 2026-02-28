from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey
from sqlalchemy import text
from sqlmodel import Session

from app.core.config import settings
from app.db.models import KidBonusTime, VideoApproval
from app.db.models import Request as ApprovalRequest
from app.db.session import get_session

router = APIRouter(prefix="/discord", tags=["discord"])
logger = logging.getLogger(__name__)


def build_approval_embed_payload(
    *,
    request_id: int,
    request_type: str,
    youtube_id: str | None,
    kid_name: str,
    video_title: str | None,
    channel_name: str | None,
) -> dict[str, object]:
    safe_video_title = video_title or "Unknown video"
    safe_channel_name = channel_name or "Unknown channel"
    safe_kid = kid_name or "Unknown kid"
    thumbnail_url = (
        f"https://i.ytimg.com/vi/{youtube_id}/hqdefault.jpg" if youtube_id else None
    )

    approve_url = f"https://discord.com/channels/@me?approve=request:{request_id}:approve"
    deny_url = f"https://discord.com/channels/@me?deny=request:{request_id}:deny"

    embed: dict[str, object] = {
        "title": f"New Request from {safe_kid}",
        "description": (
            f"Type: **{request_type}**\n"
            f"Approve: {approve_url}\n"
            f"Deny: {deny_url}"
        ),
        "color": 0x5F6DFF,
        "fields": [
            {"name": "Video title", "value": safe_video_title, "inline": False},
            {"name": "Channel name", "value": safe_channel_name, "inline": True},
            {"name": "Requested by", "value": safe_kid, "inline": True},
        ],
    }
    if thumbnail_url:
        embed["thumbnail"] = {"url": thumbnail_url}

    return {
        "embeds": [embed],
        "components": [
            {
                "type": 1,
                "components": [
                    {
                        "type": 2,
                        "style": 3,
                        "label": "Approve",
                        "custom_id": f"request:{request_id}:approve",
                    },
                    {
                        "type": 2,
                        "style": 4,
                        "label": "Deny",
                        "custom_id": f"request:{request_id}:deny",
                    },
                ],
            }
        ],
    }


def _verify_signature(body: bytes, signature: str, timestamp: str) -> None:
    verify_key = VerifyKey(bytes.fromhex(settings.discord_public_key or ""))
    verify_key.verify(f"{timestamp}".encode() + body, bytes.fromhex(signature))


def _bonus_minutes_from_code(code: str) -> int:
    if code in {"15", "30", "60"}:
        return int(code)
    if code == "today":
        now = datetime.now(timezone.utc)  # noqa: UP017
        next_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        remaining = int((next_midnight - now).total_seconds() // 60)
        return max(1, remaining)
    raise ValueError("Unsupported bonus code")


def _resolve_request_action(session: Session, request_id: int, action: str) -> None:
    request_row = session.get(ApprovalRequest, request_id)
    if not request_row:
        return

    now = datetime.now(timezone.utc)  # noqa: UP017
    if action == "deny":
        request_row.status = "denied"
        request_row.resolved_at = now
        session.add(request_row)
        session.commit()
        return

    if action != "approve":
        return

    request_row.status = "approved"
    request_row.resolved_at = now

    if request_row.type == "channel" and request_row.youtube_id:
        session.execute(
            text("UPDATE channels SET allowed = 1 WHERE youtube_id = :youtube_id"),
            {"youtube_id": request_row.youtube_id},
        )
    elif request_row.type == "video" and request_row.youtube_id:
        existing = session.execute(
            text("SELECT id FROM video_approvals WHERE youtube_id = :youtube_id LIMIT 1"),
            {"youtube_id": request_row.youtube_id},
        ).first()
        if not existing:
            session.add(VideoApproval(youtube_id=request_row.youtube_id, request_id=request_row.id))
    elif request_row.type == "bonus" and request_row.kid_id and request_row.youtube_id:
        minutes = _bonus_minutes_from_code(request_row.youtube_id)
        session.add(KidBonusTime(kid_id=request_row.kid_id, minutes=minutes, expires_at=None))

    session.add(request_row)
    session.commit()


@router.post("/interactions")
async def discord_interactions(
    request: Request,
    x_signature_ed25519: str | None = Header(default=None),
    x_signature_timestamp: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    if not x_signature_ed25519 or not x_signature_timestamp:
        raise HTTPException(status_code=401, detail="Missing signature headers")
    if not settings.discord_public_key:
        raise HTTPException(status_code=500, detail="DISCORD_PUBLIC_KEY is not configured")

    body = await request.body()
    try:
        _verify_signature(body, x_signature_ed25519, x_signature_timestamp)
    except (BadSignatureError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid request signature") from exc

    parsed_body = json.loads(body.decode() or "{}")
    logger.info("discord_interaction_received", extra={"interaction": parsed_body})

    if parsed_body.get("type") == 1:
        return {"type": 1}

    custom_id = (
        parsed_body.get("data", {}).get("custom_id")
        if isinstance(parsed_body.get("data"), dict)
        else None
    )
    if isinstance(custom_id, str):
        parts = custom_id.split(":")
        if len(parts) == 3 and parts[0] == "request":
            _resolve_request_action(session, int(parts[1]), parts[2])
        if len(parts) == 3 and parts[0] == "bonus":
            minutes = _bonus_minutes_from_code(parts[2])
            session.add(KidBonusTime(kid_id=int(parts[1]), minutes=minutes, expires_at=None))
            session.commit()

    return {"type": 4, "data": {"content": "Action processed", "flags": 64}}
