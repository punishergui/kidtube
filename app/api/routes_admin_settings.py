from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter()
APP_SETTINGS_FILE = Path('/data/app_settings.json')
LEGACY_NOTIFICATION_FILE = Path('/data/notification_settings.json')
MASK = '••••'


class AppSettingsPayload(BaseModel):
    youtube_api_key: str | None = None
    approval_email_to: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    discord_approval_webhook_url: str | None = None
    discord_bot_token: str | None = None
    discord_public_key: str | None = None
    discord_guild_id: str | None = None
    discord_approval_channel_id: str | None = None
    discord_allowed_role_ids: str | None = None
    discord_allowed_user_ids: str | None = None
    sync_max_videos_per_channel: int | None = None
    sync_interval_seconds: int | None = None
    deep_sync_enabled: bool | None = None
    app_base_url: str | None = None


class NotificationSettingsPayload(BaseModel):
    approval_email_to: str | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None
    discord_approval_webhook_url: str | None = None


def _normalize_text(value: str | None) -> str | None:
    return (value or '').strip() or None


def _load_store() -> dict[str, Any]:
    if not APP_SETTINGS_FILE.exists():
        return {}
    try:
        payload = json.loads(APP_SETTINGS_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_store(data: dict[str, Any]) -> None:
    APP_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    APP_SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')


def _current_with_fallbacks(store: dict[str, Any]) -> dict[str, Any]:
    return {
        'youtube_api_key': store.get('youtube_api_key', settings.youtube_api_key),
        'approval_email_to': store.get('approval_email_to', settings.approval_email_to),
        'smtp_host': store.get('smtp_host', settings.smtp_host),
        'smtp_port': store.get('smtp_port', settings.smtp_port),
        'smtp_username': store.get('smtp_username', settings.smtp_username),
        'smtp_password': MASK if (store.get('smtp_password') or settings.smtp_password) else None,
        'smtp_password_is_set': bool(store.get('smtp_password') or settings.smtp_password),
        'smtp_from': store.get('smtp_from', settings.smtp_from),
        'discord_approval_webhook_url': store.get(
            'discord_approval_webhook_url', settings.discord_approval_webhook_url
        ),
        'discord_bot_token': (
            MASK if (store.get('discord_bot_token') or settings.discord_bot_token) else None
        ),
        'discord_bot_token_is_set': bool(
            store.get('discord_bot_token') or settings.discord_bot_token
        ),
        'discord_public_key': store.get('discord_public_key', settings.discord_public_key),
        'discord_guild_id': store.get('discord_guild_id', settings.discord_guild_id),
        'discord_approval_channel_id': store.get(
            'discord_approval_channel_id', settings.discord_approval_channel_id
        ),
        'discord_allowed_role_ids': store.get(
            'discord_allowed_role_ids', settings.discord_allowed_role_ids
        ),
        'discord_allowed_user_ids': store.get(
            'discord_allowed_user_ids', settings.discord_allowed_user_ids
        ),
        'sync_max_videos_per_channel': store.get(
            'sync_max_videos_per_channel', settings.sync_max_videos_per_channel
        ),
        'sync_interval_seconds': store.get('sync_interval_seconds', settings.sync_interval_seconds),
        'deep_sync_enabled': store.get('deep_sync_enabled', settings.deep_sync_enabled),
        'app_base_url': store.get('app_base_url', settings.app_base_url),
    }


def _apply_runtime(data: dict[str, Any]) -> None:
    for key in (
        'youtube_api_key',
        'approval_email_to',
        'smtp_host',
        'smtp_port',
        'smtp_username',
        'smtp_password',
        'smtp_from',
        'discord_approval_webhook_url',
        'discord_bot_token',
        'discord_public_key',
        'discord_guild_id',
        'discord_approval_channel_id',
        'discord_allowed_role_ids',
        'discord_allowed_user_ids',
        'sync_max_videos_per_channel',
        'sync_interval_seconds',
        'deep_sync_enabled',
        'app_base_url',
    ):
        if key in data:
            setattr(settings, key, data[key])


@router.get('/settings')
def get_app_settings() -> dict[str, Any]:
    return _current_with_fallbacks(_load_store())


@router.post('/settings')
def save_app_settings(payload: AppSettingsPayload) -> dict[str, bool]:
    store = _load_store()
    data = payload.model_dump()

    text_fields = {
        'youtube_api_key',
        'approval_email_to',
        'smtp_host',
        'smtp_username',
        'smtp_from',
        'discord_approval_webhook_url',
        'discord_public_key',
        'discord_guild_id',
        'discord_approval_channel_id',
        'discord_allowed_role_ids',
        'discord_allowed_user_ids',
        'app_base_url',
    }

    for key, value in data.items():
        if value is None:
            continue
        if key in {'smtp_password', 'discord_bot_token'}:
            masked_or_empty = value in {MASK, ''}
            if masked_or_empty:
                continue
            store[key] = _normalize_text(value)
            continue
        if key in text_fields:
            store[key] = _normalize_text(value)
            continue
        store[key] = value

    _save_store(store)
    _apply_runtime(store)
    return {'ok': True}


@router.get('/notification-settings')
def get_notification_settings() -> dict[str, str | None]:
    data = get_app_settings()
    return {
        'approval_email_to': data.get('approval_email_to'),
        'smtp_username': data.get('smtp_username'),
        'smtp_password': data.get('smtp_password'),
        'discord_approval_webhook_url': data.get('discord_approval_webhook_url'),
    }


@router.post('/notification-settings')
def save_notification_settings(payload: NotificationSettingsPayload) -> dict[str, bool]:
    settings_payload = AppSettingsPayload(
        approval_email_to=payload.approval_email_to,
        smtp_username=payload.smtp_username,
        smtp_password=payload.smtp_password,
        discord_approval_webhook_url=payload.discord_approval_webhook_url,
    )
    return save_app_settings(settings_payload)
