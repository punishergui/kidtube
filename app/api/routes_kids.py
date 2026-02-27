from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db.models import Kid
from app.db.session import get_session

router = APIRouter()

UPLOAD_ROOT = Path(__file__).resolve().parents[1] / "static" / "uploads" / "kids"
ALLOWED_AVATAR_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}


class KidCreate(BaseModel):
    name: str
    avatar_url: str | None = None
    daily_limit_minutes: int | None = None


class KidUpdate(BaseModel):
    name: str | None = None
    avatar_url: str | None = None
    daily_limit_minutes: int | None = None


class KidRead(BaseModel):
    id: int
    name: str
    avatar_url: str | None
    daily_limit_minutes: int | None
    created_at: datetime


def _delete_avatar_files(kid_id: int) -> None:
    kid_dir = UPLOAD_ROOT / str(kid_id)
    if not kid_dir.exists():
        return

    for file_path in kid_dir.glob("avatar.*"):
        file_path.unlink(missing_ok=True)


@router.get("", response_model=list[KidRead])
def list_kids(session: Session = Depends(get_session)) -> list[Kid]:
    return session.exec(select(Kid).order_by(Kid.id)).all()


@router.post("", response_model=KidRead, status_code=status.HTTP_201_CREATED)
def create_kid(payload: KidCreate, session: Session = Depends(get_session)) -> Kid:
    kid = Kid.model_validate(payload)
    session.add(kid)
    session.commit()
    session.refresh(kid)
    return kid


@router.patch("/{kid_id}", response_model=KidRead)
def patch_kid(kid_id: int, payload: KidUpdate, session: Session = Depends(get_session)) -> Kid:
    kid = session.get(Kid, kid_id)
    if not kid:
        raise HTTPException(status_code=404, detail="Kid not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(kid, field, value)

    session.add(kid)
    session.commit()
    session.refresh(kid)
    return kid


@router.post("/{kid_id}/avatar", response_model=KidRead)
def upload_kid_avatar(
    kid_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> Kid:
    kid = session.get(Kid, kid_id)
    if not kid:
        raise HTTPException(status_code=404, detail="Kid not found")

    ext = ALLOWED_AVATAR_TYPES.get(file.content_type or "")
    if not ext:
        raise HTTPException(status_code=400, detail="Unsupported avatar file type")

    kid_dir = UPLOAD_ROOT / str(kid_id)
    kid_dir.mkdir(parents=True, exist_ok=True)
    _delete_avatar_files(kid_id)

    avatar_path = kid_dir / f"avatar.{ext}"
    avatar_path.write_bytes(file.file.read())

    timestamp = int(datetime.utcnow().timestamp())
    kid.avatar_url = f"/static/uploads/kids/{kid_id}/avatar.{ext}?v={timestamp}"
    session.add(kid)
    session.commit()
    session.refresh(kid)
    return kid


@router.delete("/{kid_id}/avatar", response_model=KidRead)
def delete_kid_avatar(kid_id: int, session: Session = Depends(get_session)) -> Kid:
    kid = session.get(Kid, kid_id)
    if not kid:
        raise HTTPException(status_code=404, detail="Kid not found")

    _delete_avatar_files(kid_id)
    kid.avatar_url = None
    session.add(kid)
    session.commit()
    session.refresh(kid)
    return kid
