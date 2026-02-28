from __future__ import annotations

from fastapi import APIRouter

from app.api.routes_categories import router as categories_router
from app.api.routes_channel_lookup import router as channel_lookup_router
from app.api.routes_channels import router as channels_router
from app.api.routes_feed import router as feed_router
from app.api.routes_kids import router as kids_router
from app.api.routes_logs import router as logs_router
from app.api.routes_playback import router as playback_router
from app.api.routes_session import router as session_router
from app.api.routes_stats import router as stats_router
from app.api.routes_sync import router as sync_router
from app.api.routes_videos import router as videos_router

api_router = APIRouter()
api_router.include_router(channels_router, prefix="/api/channels", tags=["channels"])
api_router.include_router(channel_lookup_router, prefix="/api/channel-lookup", tags=["channels"])
api_router.include_router(categories_router, prefix="/api/categories", tags=["categories"])
api_router.include_router(feed_router, prefix="/api/feed", tags=["feed"])
api_router.include_router(kids_router, prefix="/api/kids", tags=["kids"])
api_router.include_router(logs_router, prefix="/api/logs", tags=["logs"])
api_router.include_router(playback_router, prefix="/api/playback", tags=["playback"])
api_router.include_router(session_router, prefix="/api/session", tags=["session"])
api_router.include_router(stats_router, prefix="/api", tags=["stats"])
api_router.include_router(videos_router, prefix="/api/videos", tags=["videos"])

api_router.include_router(sync_router, prefix="/api/sync", tags=["sync"])
