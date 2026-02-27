from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.db.models import Channel
from app.db.session import get_session

router = APIRouter(prefix="/api/channels", tags=["channels"])


class ChannelCreate(BaseModel):
    input: str


class ChannelUpdate(BaseModel):
    enabled: bool | None = None
    category: str | None = None


class ChannelRead(BaseModel):
    id: int
    youtube_id: str
    title: str | None
    avatar_url: str | None
    banner_url: str | None
    category: str | None
    enabled: bool
    last_sync: datetime | None
    created_at: datetime


@router.get("", response_model=list[ChannelRead])
def list_channels(session: Session = Depends(get_session)) -> list[Channel]:
    return session.exec(select(Channel).order_by(Channel.id)).all()


@router.post("", response_model=ChannelRead, status_code=status.HTTP_201_CREATED)
def create_channel(
    payload: ChannelCreate,
    session: Session = Depends(get_session),
) -> Channel:
    channel = Channel(youtube_id=payload.input.strip())
    session.add(channel)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Channel already exists") from exc
    session.refresh(channel)
    return channel


@router.patch("/{channel_id}", response_model=ChannelRead)
def patch_channel(
    channel_id: int,
    payload: ChannelUpdate,
    session: Session = Depends(get_session),
) -> Channel:
    channel = session.get(Channel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(channel, field, value)

    session.add(channel)
    session.commit()
    session.refresh(channel)
    return channel
