from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel


class Kid(SQLModel, table=True):
    __tablename__ = "kids"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    avatar_url: str | None = None
    pin: str | None = None
    daily_limit_minutes: int | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Channel(SQLModel, table=True):
    __tablename__ = "channels"

    id: int | None = Field(default=None, primary_key=True)
    youtube_id: str = Field(index=True, unique=True)
    input: str | None = None
    title: str | None = None
    avatar_url: str | None = None
    banner_url: str | None = None
    category: str | None = None
    category_id: int | None = Field(default=None, foreign_key="categories.id")
    allowed: bool = False
    blocked: bool = False
    blocked_at: datetime | None = None
    blocked_reason: str | None = None
    enabled: bool = True
    last_sync: datetime | None = None
    resolved_at: datetime | None = None
    resolve_status: str = "pending"
    resolve_error: str | None = None
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
    seconds_watched: int
    category_id: int | None = Field(default=None, foreign_key="categories.id")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Category(SQLModel, table=True):
    __tablename__ = "categories"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    enabled: bool = True
    daily_limit_minutes: int | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class KidSchedule(SQLModel, table=True):
    __tablename__ = "kid_schedules"

    id: int | None = Field(default=None, primary_key=True)
    kid_id: int = Field(foreign_key="kids.id", index=True)
    day_of_week: int = Field(index=True)
    start_time: str
    end_time: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class KidCategoryLimit(SQLModel, table=True):
    __tablename__ = "kid_category_limits"

    id: int | None = Field(default=None, primary_key=True)
    kid_id: int = Field(foreign_key="kids.id", index=True)
    category_id: int = Field(foreign_key="categories.id", index=True)
    daily_limit_minutes: int
    created_at: datetime = Field(default_factory=datetime.utcnow)


class KidBonusTime(SQLModel, table=True):
    __tablename__ = "kid_bonus_time"

    id: int | None = Field(default=None, primary_key=True)
    kid_id: int = Field(foreign_key="kids.id", index=True)
    minutes: int
    expires_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SearchLog(SQLModel, table=True):
    __tablename__ = "search_log"

    id: int | None = Field(default=None, primary_key=True)
    kid_id: int = Field(foreign_key="kids.id", index=True)
    query: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Request(SQLModel, table=True):
    __tablename__ = "requests"

    id: int | None = Field(default=None, primary_key=True)
    type: str
    youtube_id: str
    kid_id: int | None = Field(default=None, foreign_key="kids.id")
    status: str = "pending"
    created_at: datetime = Field(default_factory=datetime.utcnow)
