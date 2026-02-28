from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.core.config import settings
from app.db.models import Kid
from app.db.session import get_session
from app.services.security import hash_pin, verify_pin_hash

router = APIRouter()
ADMIN_PIN_FILE = Path('/data/admin_pin.json')


class SelectKidPayload(BaseModel):
    kid_id: int


class VerifyPinPayload(BaseModel):
    pin: str


class AdminPinPayload(BaseModel):
    new_pin: str = Field(min_length=4, max_length=6)
    current_pin: str = ""


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
    if not kid or not verify_pin_hash(kid.pin, payload.pin):
        raise HTTPException(status_code=403, detail="Invalid PIN")

    request.session["kid_id"] = pending_kid_id
    request.session.pop("pending_kid_id", None)
    return {"kid_id": pending_kid_id, "ok": True}


@router.post("/admin-verify")
def admin_verify(payload: VerifyPinPayload, request: Request) -> dict[str, bool]:
    configured_pin = settings.admin_pin or ""
    if not configured_pin:
        request.session["is_admin"] = True
        return {"ok": True, "no_pin": True}

    plain_pin = payload.pin or ""
    is_valid = verify_pin_hash(configured_pin, plain_pin) or configured_pin == plain_pin
    if not is_valid:
        raise HTTPException(status_code=403, detail="Invalid admin PIN")

    request.session["is_admin"] = True
    return {"ok": True}


@router.get('/admin-pin')
def admin_pin_status() -> dict[str, bool]:
    return {"is_set": bool(settings.admin_pin)}


@router.post('/admin-pin')
def set_admin_pin(payload: AdminPinPayload, request: Request) -> dict[str, bool]:
    if not payload.new_pin.isdigit() or len(payload.new_pin) < 4 or len(payload.new_pin) > 6:
        raise HTTPException(status_code=400, detail='PIN must be 4-6 digits')

    is_admin = bool(request.session.get('is_admin'))
    configured_pin = settings.admin_pin or ''
    has_current_match = bool(configured_pin and verify_pin_hash(configured_pin, payload.current_pin))

    if configured_pin and not is_admin and not has_current_match:
        raise HTTPException(status_code=403, detail='Current admin PIN required')

    hashed = hash_pin(payload.new_pin)
    ADMIN_PIN_FILE.parent.mkdir(parents=True, exist_ok=True)
    ADMIN_PIN_FILE.write_text(json.dumps({'admin_pin': hashed}), encoding='utf-8')
    settings.admin_pin = hashed
    request.session['is_admin'] = True
    return {'ok': True}


@router.delete('/admin-pin')
def delete_admin_pin(request: Request) -> dict[str, bool]:
    if not request.session.get('is_admin'):
        raise HTTPException(status_code=403, detail='Admin session required')

    if ADMIN_PIN_FILE.exists():
        ADMIN_PIN_FILE.unlink()
    settings.admin_pin = None
    return {'ok': True}


@router.post("/logout")
def logout(request: Request) -> dict[str, bool]:
    request.session.pop("kid_id", None)
    request.session.pop("pending_kid_id", None)
    return {"ok": True}
