from __future__ import annotations

from fastapi import APIRouter

from app.api.routes_channels import router as channels_router
from app.api.routes_feed import router as feed_router
from app.api.routes_kids import router as kids_router

api_router = APIRouter()
api_router.include_router(kids_router)
api_router.include_router(channels_router)
api_router.include_router(feed_router)
