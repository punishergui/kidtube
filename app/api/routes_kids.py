from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db.models import Kid
from app.db.session import get_session

router = APIRouter()

ALLOWED_AVATAR_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
}


class KidCreate(BaseModel):
    name: str
    avatar_url: str | None = None
    daily_limit_minutes: int | None = None
    pin: str | None = None


class KidUpdate(BaseModel):
    name: str | None = None
    avatar_url: str | None = None
    daily_limit_minutes: int | None = None
    pin: str | None = None


class KidRead(BaseModel):
    id: int
    name: str
    avatar_url: str | None
    daily_limit_minutes: int | None
    created_at: datetime
    has_pin: bool = False


def _avatar_path(kid_id: int) -> Path:
    app_dir = Path(__file__).resolve().parents[1]
    upload_dir = app_dir / "static" / "uploads" / "kids" / str(kid_id)
    return upload_dir / "avatar.png"


def _delete_avatar_file(kid_id: int) -> None:
    avatar_path = _avatar_path(kid_id)
    avatar_path.unlink(missing_ok=True)


def _to_kid_read(kid: Kid) -> KidRead:
    return KidRead(
        id=kid.id,
        name=kid.name,
        avatar_url=kid.avatar_url,
        daily_limit_minutes=kid.daily_limit_minutes,
        created_at=kid.created_at,
        has_pin=bool(kid.pin_hash),
    )


@router.get("", response_model=list[KidRead])
def list_kids(session: Session = Depends(get_session)) -> list[KidRead]:
    kids = session.exec(select(Kid).order_by(Kid.id)).all()
    return [_to_kid_read(kid) for kid in kids]


@router.post("", response_model=KidRead, status_code=status.HTTP_201_CREATED)
def create_kid(payload: KidCreate, session: Session = Depends(get_session)) -> KidRead:
    data = payload.model_dump()
    data['pin_hash'] = data.pop('pin')
    kid = Kid.model_validate(data)
    session.add(kid)
    session.commit()
    session.refresh(kid)
    return _to_kid_read(kid)


@router.patch("/{kid_id}", response_model=KidRead)
def patch_kid(kid_id: int, payload: KidUpdate, session: Session = Depends(get_session)) -> KidRead:
    kid = session.get(Kid, kid_id)
    if not kid:
        raise HTTPException(status_code=404, detail="Kid not found")

    updates = payload.model_dump(exclude_unset=True)
    if 'pin' in updates:
        updates['pin_hash'] = updates.pop('pin')
    for field, value in updates.items():
        setattr(kid, field, value)

    session.add(kid)
    session.commit()
    session.refresh(kid)
    return _to_kid_read(kid)


@router.post("/{kid_id}/avatar", response_model=KidRead)
async def upload_kid_avatar(
    kid_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> KidRead:
    kid = session.get(Kid, kid_id)
    if not kid:
        raise HTTPException(status_code=404, detail="Kid not found")

    if (file.content_type or "") not in ALLOWED_AVATAR_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported avatar file type")

    app_dir = Path(__file__).resolve().parents[1]
    upload_dir = app_dir / "static" / "uploads" / "kids" / str(kid_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    avatar_path = upload_dir / "avatar.png"
    data = await file.read()
    avatar_path.write_bytes(data)

    timestamp = int(datetime.utcnow().timestamp())
    kid.avatar_url = f"/static/uploads/kids/{kid_id}/avatar.png?v={timestamp}"
    session.add(kid)
    session.commit()
    session.refresh(kid)
    return _to_kid_read(kid)


@router.delete("/{kid_id}/avatar", response_model=KidRead)
def delete_kid_avatar(kid_id: int, session: Session = Depends(get_session)) -> KidRead:
    kid = session.get(Kid, kid_id)
    if not kid:
        raise HTTPException(status_code=404, detail="Kid not found")

    _delete_avatar_file(kid_id)
    kid.avatar_url = None
    session.add(kid)
    session.commit()
    session.refresh(kid)
    return _to_kid_read(kid)
