from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.sync import refresh_enabled_channels, refresh_enabled_channels_deep

router = APIRouter()


class SyncFailure(BaseModel):
    id: int | None
    input: str | None
    error: str


class SyncSummary(BaseModel):
    channels_seen: int
    resolved: int
    synced: int
    failed: int
    failures: list[SyncFailure]


@router.post("/run", response_model=SyncSummary)
async def run_sync() -> SyncSummary:
    summary = await refresh_enabled_channels()
    return SyncSummary.model_validate(summary)


@router.post("/deep", response_model=SyncSummary)
async def run_deep_sync() -> SyncSummary:
    summary = await refresh_enabled_channels_deep()
    return SyncSummary.model_validate(summary)
