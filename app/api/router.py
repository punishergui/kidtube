from __future__ import annotations

from fastapi import APIRouter

from app.api.routes_categories import router as categories_router
from app.api.routes_channel_lookup import router as channel_lookup_router
from app.api.routes_channels import router as channels_router
from app.api.routes_feed import router as feed_router
from app.api.routes_kids import router as kids_router
from app.api.routes_sync import router as sync_router
from app.api.routes_videos import router as videos_router

api_router = APIRouter()
api_router.include_router(channels_router, prefix="/api/channels", tags=["channels"])
api_router.include_router(channel_lookup_router, prefix="/api/channel-lookup", tags=["channels"])
api_router.include_router(categories_router, prefix="/api/categories", tags=["categories"])
api_router.include_router(feed_router, prefix="/api/feed", tags=["feed"])
api_router.include_router(kids_router, prefix="/api/kids", tags=["kids"])
api_router.include_router(videos_router, prefix="/api/videos", tags=["videos"])

api_router.include_router(sync_router, prefix="/api/sync", tags=["sync"])
