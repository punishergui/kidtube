from __future__ import annotations

from fastapi import APIRouter

from app.api.routes_channels import router as channels_router
from app.api.routes_feed import router as feed_router
from app.api.routes_kids import router as kids_router
from app.api.routes_sync import router as sync_router

api_router = APIRouter()
api_router.include_router(channels_router, prefix="/api/channels", tags=["channels"])
api_router.include_router(feed_router, prefix="/api/feed", tags=["feed"])
api_router.include_router(kids_router, prefix="/api/kids", tags=["kids"])

api_router.include_router(sync_router, prefix="/api/sync", tags=["sync"])
