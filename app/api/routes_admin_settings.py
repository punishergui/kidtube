from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter()
SETTINGS_FILE = Path('/data/notification_settings.json')


class NotificationSettingsPayload(BaseModel):
    approval_email_to: str | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None
    discord_approval_webhook_url: str | None = None


@router.get('/notification-settings')
def get_notification_settings() -> dict[str, str | None]:
    return {
        'approval_email_to': settings.approval_email_to,
        'smtp_username': settings.smtp_username,
        'smtp_password': '••••' if settings.smtp_password else None,
        'discord_approval_webhook_url': settings.discord_approval_webhook_url,
    }


@router.post('/notification-settings')
def save_notification_settings(payload: NotificationSettingsPayload) -> dict[str, bool]:
    data = {
        'approval_email_to': (payload.approval_email_to or '').strip() or None,
        'smtp_username': (payload.smtp_username or '').strip() or None,
        'smtp_password': (payload.smtp_password or '').strip() or None,
        'discord_approval_webhook_url': (
            (payload.discord_approval_webhook_url or '').strip() or None
        ),
    }

    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')

    settings.approval_email_to = data['approval_email_to']
    settings.smtp_username = data['smtp_username']
    settings.smtp_password = data['smtp_password']
    settings.discord_approval_webhook_url = data['discord_approval_webhook_url']

    return {'ok': True}
