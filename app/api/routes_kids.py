from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session, select

from app.db.models import Kid, KidBonusTime
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
    bedtime_start: str | None = None
    bedtime_end: str | None = None


class KidUpdate(BaseModel):
    name: str | None = None
    avatar_url: str | None = None
    daily_limit_minutes: int | None = None
    bedtime_start: str | None = None
    bedtime_end: str | None = None


class KidRead(BaseModel):
    id: int
    name: str
    avatar_url: str | None
    daily_limit_minutes: int | None
    bedtime_start: str | None
    bedtime_end: str | None
    created_at: datetime


class KidBonusTimeCreate(BaseModel):
    minutes: int
    expires_at: datetime | None = None


class KidBonusTimeRead(BaseModel):
    id: int
    kid_id: int
    minutes: int
    expires_at: datetime | None
    created_at: datetime


def _avatar_path(kid_id: int) -> Path:
    app_dir = Path(__file__).resolve().parents[1]
    upload_dir = app_dir / "static" / "uploads" / "kids" / str(kid_id)
    return upload_dir / "avatar.png"


def _delete_avatar_file(kid_id: int) -> None:
    avatar_path = _avatar_path(kid_id)
    avatar_path.unlink(missing_ok=True)


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




@router.post(
    "/{kid_id}/bonus-time",
    response_model=KidBonusTimeRead,
    status_code=status.HTTP_201_CREATED,
)
def create_kid_bonus_time(
    kid_id: int,
    payload: KidBonusTimeCreate,
    session: Session = Depends(get_session),
) -> KidBonusTime:
    kid = session.get(Kid, kid_id)
    if not kid:
        raise HTTPException(status_code=404, detail="Kid not found")

    if payload.minutes <= 0:
        raise HTTPException(status_code=400, detail="minutes must be greater than 0")

    now = datetime.now(timezone.utc)  # noqa: UP017
    expires_at = payload.expires_at
    if expires_at is None:
        expires_at = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

    bonus_time = KidBonusTime(
        kid_id=kid_id,
        minutes=payload.minutes,
        expires_at=expires_at,
    )
    session.add(bonus_time)
    session.commit()
    session.refresh(bonus_time)
    return bonus_time


@router.get("/{kid_id}/bonus-time", response_model=list[KidBonusTimeRead])
def list_kid_bonus_time(kid_id: int, session: Session = Depends(get_session)) -> list[KidBonusTime]:
    kid = session.get(Kid, kid_id)
    if not kid:
        raise HTTPException(status_code=404, detail="Kid not found")

    now = datetime.now(timezone.utc)  # noqa: UP017
    query = text(
        """
        SELECT id, kid_id, minutes, expires_at, created_at
        FROM kid_bonus_time
        WHERE kid_id = :kid_id
          AND (expires_at IS NULL OR expires_at > :now)
        ORDER BY created_at DESC
        """
    )
    rows = session.execute(query, {"kid_id": kid_id, "now": now.isoformat()}).mappings().all()
    return [KidBonusTime.model_validate(row) for row in rows]


@router.post("/{kid_id}/avatar", response_model=KidRead)
async def upload_kid_avatar(
    kid_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> Kid:
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
    return kid


@router.delete("/{kid_id}/avatar", response_model=KidRead)
def delete_kid_avatar(kid_id: int, session: Session = Depends(get_session)) -> Kid:
    kid = session.get(Kid, kid_id)
    if not kid:
        raise HTTPException(status_code=404, detail="Kid not found")

    _delete_avatar_file(kid_id)
    kid.avatar_url = None
    session.add(kid)
    session.commit()
    session.refresh(kid)
    return kid
