from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel


class Kid(SQLModel, table=True):
    __tablename__ = "kids"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    avatar_url: str | None = None
    daily_limit_minutes: int | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Channel(SQLModel, table=True):
    __tablename__ = "channels"

    id: int | None = Field(default=None, primary_key=True)
    youtube_id: str = Field(index=True, unique=True)
    title: str | None = None
    avatar_url: str | None = None
    banner_url: str | None = None
    category: str | None = None
    enabled: bool = True
    last_sync: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Video(SQLModel, table=True):
    __tablename__ = "videos"

    id: int | None = Field(default=None, primary_key=True)
    youtube_id: str = Field(index=True, unique=True)
    channel_id: int = Field(foreign_key="channels.id")
    title: str
    thumbnail_url: str
    published_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WatchLog(SQLModel, table=True):
    __tablename__ = "watch_log"

    id: int | None = Field(default=None, primary_key=True)
    kid_id: int = Field(foreign_key="kids.id")
    video_id: int = Field(foreign_key="videos.id")
    watched_seconds: int
    watched_at: datetime = Field(default_factory=datetime.utcnow)


class Request(SQLModel, table=True):
    __tablename__ = "requests"

    id: int | None = Field(default=None, primary_key=True)
    type: str
    youtube_id: str
    kid_id: int | None = Field(default=None, foreign_key="kids.id")
    status: str = "pending"
    created_at: datetime = Field(default_factory=datetime.utcnow)
