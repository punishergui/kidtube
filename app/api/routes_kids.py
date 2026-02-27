from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db.models import Kid
from app.db.session import get_session

router = APIRouter()


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
