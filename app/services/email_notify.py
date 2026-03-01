from __future__ import annotations

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_approval_request_email(
    request_id: int,
    request_type: str,
    youtube_id: str | None,
    kid_name: str,
    video_title: str | None,
    channel_name: str | None,
    thumbnail_url: str | None = None,
) -> None:
    if not settings.approval_email_to:
        logger.info("approval_email_not_configured")
        return

    if not settings.smtp_username or not settings.smtp_password or not settings.smtp_from:
        logger.info("smtp_not_fully_configured", extra={"request_id": request_id})
        return

    approvals_url = f"{settings.app_base_url.rstrip('/')}/admin/approvals"
    safe_title = video_title or youtube_id or "requested content"
    subject = f"KidTube: {kid_name} wants to watch {safe_title}"

    plain = (
        "KidTube approval request\n\n"
        f"Kid: {kid_name}\n"
        f"Type: {request_type}\n"
        f"Title: {safe_title}\n"
        f"Channel: {channel_name or 'Unknown'}\n"
        f"Request ID: {request_id}\n\n"
        f"Approve or deny: {approvals_url}\n"
    )

    image = ""
    if thumbnail_url:
        image = (
            f'<img src="{thumbnail_url}" alt="thumbnail" '
            'style="max-width:100%;border-radius:12px;margin:12px 0;" />'
        )

    html = f"""
    <html><body
      style=\"font-family:Arial,sans-serif;background:#0f172a;color:#e5e7eb;padding:20px;\">
      <div
        style=\"max-width:620px;margin:auto;background:#111827;padding:20px;\">
        <h2 style=\"margin:0 0 8px;\">KidTube Approval Request</h2>
        <p style=\"margin:0 0 8px;color:#cbd5e1;\">
          <strong>{kid_name}</strong> requested new content.
        </p>
        <p style=\"margin:0;color:#cbd5e1;\">Title: <strong>{safe_title}</strong></p>
        <p style=\"margin:6px 0 0;color:#cbd5e1;\">
          Channel: <strong>{channel_name or 'Unknown'}</strong>
        </p>
        {image}
        <div style=\"display:flex;gap:12px;margin-top:16px;\">
          <a href=\"{approvals_url}\"
            style=\"background:#16a34a;color:#fff;padding:12px 16px;\">
            ✅ Approve
          </a>
          <a href=\"{approvals_url}\"
            style=\"background:#dc2626;color:#fff;padding:12px 16px;\">
            ❌ Deny
          </a>
        </div>
      </div>
    </body></html>
    """

    def _send() -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from or ""
        msg["To"] = settings.approval_email_to or ""
        msg.attach(MIMEText(plain, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(settings.smtp_from, [settings.approval_email_to], msg.as_string())

    try:
        await asyncio.to_thread(_send)
        logger.info(
            "approval_email_sent",
            extra={"request_id": request_id, "to": settings.approval_email_to},
        )
    except Exception as exc:
        logger.error(
            "approval_email_send_failed",
            extra={"request_id": request_id, "error": str(exc)},
        )
