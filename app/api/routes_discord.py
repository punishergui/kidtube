from datetime import datetime
import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey
from sqlmodel import Session, select

from app.core.config import settings
from app.db.models import Channel, KidBonusTime, Request as ApprovalRequest, VideoApproval
from app.db.session import get_session

router = APIRouter(prefix="/discord", tags=["discord"])
logger = logging.getLogger(__name__)


def _handle_action(custom_id: str, session: Session) -> None:
    parts = custom_id.split(':')
    if len(parts) < 3:
        return
    action, resource, resource_id = parts[0], parts[1], parts[2]

    if action in {'approve', 'deny'} and resource == 'channel':
        channel = session.exec(select(Channel).where(Channel.youtube_id == resource_id)).first()
        if channel:
            channel.allowed = action == 'approve'
            channel.blocked = action == 'deny'
            session.add(channel)

    if action in {'approve', 'deny'} and resource == 'video':
        approval = session.exec(select(VideoApproval).where(VideoApproval.youtube_id == resource_id)).first()
        if not approval:
            approval = VideoApproval(youtube_id=resource_id)
        approval.allowed = action == 'approve'
        session.add(approval)

    if action == 'bonus' and resource == 'kid' and len(parts) >= 4:
        minutes = int(parts[3])
        grant = KidBonusTime(
            kid_id=int(resource_id),
            minutes=minutes,
            expires_at=datetime.utcnow().replace(hour=23, minute=59, second=59, microsecond=0),
        )
        session.add(grant)

    session.commit()


@router.post("/interactions")
async def discord_interactions(
    request: Request,
    x_signature_ed25519: str | None = Header(default=None),
    x_signature_timestamp: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    if not x_signature_ed25519 or not x_signature_timestamp:
        raise HTTPException(status_code=401, detail="Missing signature headers")
    if not settings.discord_public_key:
        raise HTTPException(status_code=500, detail="DISCORD_PUBLIC_KEY is not configured")

    body = await request.body()
    verify_key = VerifyKey(bytes.fromhex(settings.discord_public_key))

    try:
        verify_key.verify(
            f"{x_signature_timestamp}".encode() + body,
            bytes.fromhex(x_signature_ed25519),
        )
    except BadSignatureError as exc:
        raise HTTPException(status_code=401, detail="Invalid request signature") from exc

    parsed_body = json.loads(body.decode() or "{}")
    custom_id = parsed_body.get('data', {}).get('custom_id')
    if custom_id:
        _handle_action(custom_id, session)

    interaction_type = parsed_body.get('type')
    if interaction_type == 1:
        return {"type": 1}

    logger.info("discord_interaction_received", extra={"interaction": parsed_body})
    return {"status": "received"}
