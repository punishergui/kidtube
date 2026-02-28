from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session

from app.db.models import Kid
from app.db.session import get_session

router = APIRouter()


class SelectKidPayload(BaseModel):
    kid_id: int


class VerifyPinPayload(BaseModel):
    pin: str


@router.get("")
def get_session_state(request: Request) -> dict[str, int | None]:
    return {
        "kid_id": request.session.get("kid_id"),
        "pending_kid_id": request.session.get("pending_kid_id"),
    }


@router.post("/kid")
def select_kid(
    payload: SelectKidPayload,
    request: Request,
    session: Session = Depends(get_session),
) -> dict[str, int | bool]:
    kid = session.get(Kid, payload.kid_id)
    if not kid:
        raise HTTPException(status_code=404, detail="Kid not found")

    if kid.pin:
        request.session["pending_kid_id"] = kid.id
        request.session.pop("kid_id", None)
        return {"kid_id": kid.id, "pin_required": True}

    request.session["kid_id"] = kid.id
    request.session.pop("pending_kid_id", None)
    return {"kid_id": kid.id, "pin_required": False}


@router.post("/kid/verify-pin")
def verify_pin(
    payload: VerifyPinPayload,
    request: Request,
    session: Session = Depends(get_session),
) -> dict[str, int | bool]:
    pending_kid_id = request.session.get("pending_kid_id")
    if not pending_kid_id:
        raise HTTPException(status_code=400, detail="No pending kid selection")

    kid = session.get(Kid, pending_kid_id)
    if not kid or kid.pin != payload.pin:
        raise HTTPException(status_code=403, detail="Invalid PIN")

    request.session["kid_id"] = pending_kid_id
    request.session.pop("pending_kid_id", None)
    return {"kid_id": pending_kid_id, "ok": True}


@router.post("/logout")
def logout(request: Request) -> dict[str, bool]:
    request.session.pop("kid_id", None)
    request.session.pop("pending_kid_id", None)
    return {"ok": True}
