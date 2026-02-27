import json
import logging

from fastapi import APIRouter, Header, HTTPException, Request
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from app.core.config import settings

router = APIRouter(prefix="/discord", tags=["discord"])
logger = logging.getLogger(__name__)


@router.post("/interactions")
async def discord_interactions(
    request: Request,
    x_signature_ed25519: str | None = Header(default=None),
    x_signature_timestamp: str | None = Header(default=None),
) -> dict[str, str]:
    if not x_signature_ed25519 or not x_signature_timestamp:
        raise HTTPException(status_code=401, detail="Missing signature headers")
    if not settings.discord_public_key:
        raise HTTPException(status_code=500, detail="DISCORD_PUBLIC_KEY is not configured")

    body = await request.body()
    verify_key = VerifyKey(bytes.fromhex(settings.discord_public_key))

    try:
        verify_key.verify(f"{x_signature_timestamp}".encode() + body, bytes.fromhex(x_signature_ed25519))
    except BadSignatureError as exc:
        raise HTTPException(status_code=401, detail="Invalid request signature") from exc

    parsed_body = json.loads(body.decode() or "{}")
    logger.info("discord_interaction_received", extra={"interaction": parsed_body})
    return {"status": "received"}
