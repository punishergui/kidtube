from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlmodel import Session, select

from app.db.models import Kid, KidBonusTime, KidSchedule
from app.db.session import get_session
from app.services.security import hash_pin

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
    has_pin: bool = False
    created_at: datetime


class KidPinPayload(BaseModel):
    pin: str = Field(min_length=4, max_length=12)


class KidBonusTimeCreate(BaseModel):
    minutes: int
    expires_at: datetime | None = None


class KidBonusTimeRead(BaseModel):
    id: int
    kid_id: int
    minutes: int
    expires_at: datetime | None
    created_at: datetime


class KidScheduleCreate(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    start_time: str
    end_time: str


class KidScheduleRead(BaseModel):
    id: int
    kid_id: int
    day_of_week: int
    start_time: str
    end_time: str
    created_at: datetime


class KidCategoryLimitUpdate(BaseModel):
    daily_limit_minutes: int = Field(ge=0)


AVATAR_ROOT = Path("/data/avatars/kids")


def _avatar_path(kid_id: int) -> Path:
    upload_dir = AVATAR_ROOT / str(kid_id)
    return upload_dir / "avatar.png"


def _delete_avatar_file(kid_id: int) -> None:
    avatar_path = _avatar_path(kid_id)
    avatar_path.unlink(missing_ok=True)


def _safe_avatar_url(kid_id: int, avatar_url: str | None) -> str | None:
    if not avatar_url:
        return None
    if avatar_url.startswith('/static/uploads/kids/') and not _avatar_path(kid_id).exists():
        return None
    return avatar_url


def _assert_kid_exists(session: Session, kid_id: int) -> Kid:
    kid = session.get(Kid, kid_id)
    if not kid:
        raise HTTPException(status_code=404, detail="Kid not found")
    return kid


@router.get("", response_model=list[KidRead])
def list_kids(session: Session = Depends(get_session)) -> list[Kid]:
    kids = session.exec(select(Kid).order_by(Kid.id)).all()
    return [
        KidRead.model_validate(
            {
                **kid.model_dump(),
                "avatar_url": _safe_avatar_url(kid.id or 0, kid.avatar_url),
                "has_pin": bool(kid.pin),
            }
        )
        for kid in kids
    ]


@router.post("", response_model=KidRead, status_code=status.HTTP_201_CREATED)
def create_kid(payload: KidCreate, session: Session = Depends(get_session)) -> Kid:
    kid = Kid.model_validate(payload)
    session.add(kid)
    session.commit()
    session.refresh(kid)
    return KidRead.model_validate(
        {
            **kid.model_dump(),
            "avatar_url": _safe_avatar_url(kid.id or 0, kid.avatar_url),
            "has_pin": bool(kid.pin),
        }
    )


@router.patch("/{kid_id}", response_model=KidRead)
def patch_kid(kid_id: int, payload: KidUpdate, session: Session = Depends(get_session)) -> Kid:
    kid = _assert_kid_exists(session, kid_id)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(kid, field, value)

    session.add(kid)
    session.commit()
    session.refresh(kid)
    return KidRead.model_validate(
        {
            **kid.model_dump(),
            "avatar_url": _safe_avatar_url(kid.id or 0, kid.avatar_url),
            "has_pin": bool(kid.pin),
        }
    )


@router.put("/{kid_id}/pin")
def set_kid_pin(
    kid_id: int,
    payload: KidPinPayload,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    kid = _assert_kid_exists(session, kid_id)
    pin = payload.pin.strip()
    if not pin.isdigit():
        raise HTTPException(status_code=400, detail="PIN must be numeric")
    kid.pin = hash_pin(pin)
    session.add(kid)
    session.commit()
    return {"ok": True}


@router.delete("/{kid_id}/pin")
def remove_kid_pin(kid_id: int, session: Session = Depends(get_session)) -> dict[str, bool]:
    kid = _assert_kid_exists(session, kid_id)
    kid.pin = None
    session.add(kid)
    session.commit()
    return {"ok": True}


@router.get("/{kid_id}/schedules", response_model=list[KidScheduleRead])
def list_kid_schedules(kid_id: int, session: Session = Depends(get_session)) -> list[KidSchedule]:
    _assert_kid_exists(session, kid_id)
    return session.exec(
        select(KidSchedule)
        .where(KidSchedule.kid_id == kid_id)
        .order_by(KidSchedule.day_of_week, KidSchedule.start_time)
    ).all()


@router.post(
    "/{kid_id}/schedules", response_model=KidScheduleRead, status_code=status.HTTP_201_CREATED
)
def create_kid_schedule(
    kid_id: int,
    payload: KidScheduleCreate,
    session: Session = Depends(get_session),
) -> KidSchedule:
    _assert_kid_exists(session, kid_id)
    schedule = KidSchedule(kid_id=kid_id, **payload.model_dump())
    session.add(schedule)
    session.commit()
    session.refresh(schedule)
    return schedule


@router.delete("/{kid_id}/schedules/{schedule_id}")
def delete_kid_schedule(
    kid_id: int, schedule_id: int, session: Session = Depends(get_session)
) -> dict[str, bool]:
    _assert_kid_exists(session, kid_id)
    schedule = session.get(KidSchedule, schedule_id)
    if not schedule or schedule.kid_id != kid_id:
        raise HTTPException(status_code=404, detail="Schedule not found")

    session.delete(schedule)
    session.commit()
    return {"ok": True}


@router.get("/{kid_id}/category-limits")
def list_kid_category_limits(
    kid_id: int, session: Session = Depends(get_session)
) -> list[dict[str, object]]:
    _assert_kid_exists(session, kid_id)
    rows = (
        session.execute(
            text(
                """
            SELECT kcl.category_id, c.name AS category_name, kcl.daily_limit_minutes
            FROM kid_category_limits kcl
            INNER JOIN categories c ON c.id = kcl.category_id
            WHERE kcl.kid_id = :kid_id
            ORDER BY c.name
            """
            ),
            {"kid_id": kid_id},
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


@router.put("/{kid_id}/category-limits/{category_id}")
def upsert_kid_category_limit(
    kid_id: int,
    category_id: int,
    payload: KidCategoryLimitUpdate,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    _assert_kid_exists(session, kid_id)
    category_exists = session.execute(
        text("SELECT 1 FROM categories WHERE id = :category_id LIMIT 1"),
        {"category_id": category_id},
    ).first()
    if not category_exists:
        raise HTTPException(status_code=404, detail="Category not found")

    existing = session.execute(
        text(
            """
            SELECT id
            FROM kid_category_limits
            WHERE kid_id = :kid_id AND category_id = :category_id
            LIMIT 1
            """
        ),
        {"kid_id": kid_id, "category_id": category_id},
    ).first()

    if existing:
        session.execute(
            text(
                """
                UPDATE kid_category_limits
                SET daily_limit_minutes = :daily_limit_minutes
                WHERE id = :id
                """
            ),
            {"daily_limit_minutes": payload.daily_limit_minutes, "id": existing[0]},
        )
    else:
        session.execute(
            text(
                """
                INSERT INTO kid_category_limits(kid_id, category_id, daily_limit_minutes)
                VALUES (:kid_id, :category_id, :daily_limit_minutes)
                """
            ),
            {
                "kid_id": kid_id,
                "category_id": category_id,
                "daily_limit_minutes": payload.daily_limit_minutes,
            },
        )

    session.commit()
    return {"ok": True}


@router.delete("/{kid_id}/category-limits/{category_id}")
def delete_kid_category_limit(
    kid_id: int, category_id: int, session: Session = Depends(get_session)
) -> dict[str, bool]:
    _assert_kid_exists(session, kid_id)
    session.execute(
        text(
            """
            DELETE FROM kid_category_limits
            WHERE kid_id = :kid_id AND category_id = :category_id
            """
        ),
        {"kid_id": kid_id, "category_id": category_id},
    )
    session.commit()
    return {"ok": True}


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
    _assert_kid_exists(session, kid_id)

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
    _assert_kid_exists(session, kid_id)

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
    kid = _assert_kid_exists(session, kid_id)

    if (file.content_type or "") not in ALLOWED_AVATAR_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported avatar file type")

    avatar_path = _avatar_path(kid_id)
    upload_dir = avatar_path.parent
    upload_dir.mkdir(parents=True, exist_ok=True)
    data = await file.read()
    avatar_path.write_bytes(data)

    timestamp = int(datetime.now(datetime.UTC).timestamp())
    kid.avatar_url = f"/static/uploads/kids/{kid_id}/avatar.png?v={timestamp}"
    session.add(kid)
    session.commit()
    session.refresh(kid)
    return KidRead.model_validate(
        {
            **kid.model_dump(),
            "avatar_url": _safe_avatar_url(kid.id or 0, kid.avatar_url),
            "has_pin": bool(kid.pin),
        }
    )


@router.delete("/{kid_id}/avatar", response_model=KidRead)
def delete_kid_avatar(kid_id: int, session: Session = Depends(get_session)) -> Kid:
    kid = _assert_kid_exists(session, kid_id)

    _delete_avatar_file(kid_id)
    kid.avatar_url = None
    session.add(kid)
    session.commit()
    session.refresh(kid)
    return KidRead.model_validate(
        {
            **kid.model_dump(),
            "avatar_url": _safe_avatar_url(kid.id or 0, kid.avatar_url),
            "has_pin": bool(kid.pin),
        }
    )
