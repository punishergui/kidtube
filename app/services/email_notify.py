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
    base_url: str,
) -> None:
    if not settings.smtp_username or not settings.approval_email_to:
        logger.info("approval_email_not_configured", extra={"request_id": request_id})
        return

    subject_title = video_title or youtube_id or "requested content"
    subject = f"KidTube: {kid_name} wants to watch {subject_title}"
    thumbnail = (
        f"https://img.youtube.com/vi/{youtube_id}/hqdefault.jpg"
        if youtube_id
        else "https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg"
    )
    approvals_url = f"{base_url.rstrip('/')}/admin/approvals"

    plain = (
        "KidTube approval request\n\n"
        f"Kid: {kid_name}\n"
        f"Type: {request_type}\n"
        f"Video: {subject_title}\n"
        f"Channel: {channel_name or 'Unknown'}\n"
        f"Review: {approvals_url}\n\n"
        "Sent by KidTube parental controls"
    )

    kid_line = f"<strong>{kid_name}</strong> asked to watch new content."
    channel_label = channel_name or "Unknown"

    html = (
        "<html><body "
        "style='margin:0;background:#0b1020;color:#e5e7eb;font-family:Inter,Arial,sans-serif;'>"
        "<div style='max-width:640px;margin:0 auto;padding:24px;'>"
        "<div style='background:#111827;border:1px solid #2b354f;border-radius:16px;padding:20px;'>"
        "<h2 style='margin:0 0 12px;color:#f8fafc;'>KidTube Approval Request</h2>"
        f"<p style='margin:0 0 8px;color:#cbd5e1;'>{kid_line}</p>"
        f"<p style='margin:0 0 6px;color:#cbd5e1;'><strong>Title:</strong> {subject_title}</p>"
        f"<p style='margin:0 0 16px;color:#cbd5e1;'><strong>Channel:</strong> {channel_label}</p>"
        f"<img src='{thumbnail}' alt='Video thumbnail' "
        "style='width:100%;max-width:560px;border-radius:12px;display:block;' />"
        "<div style='margin-top:18px;'>"
        f"<a href='{approvals_url}' style='display:inline-block;background:#7c5cff;color:#fff;"
        "text-decoration:none;font-weight:700;padding:12px 18px;border-radius:10px;'>"
        "Review Request →</a></div></div>"
        "<p style='color:#94a3b8;font-size:12px;margin-top:12px;'>"
        "Sent by KidTube parental controls</p></div></body></html>"
    )

    def _send_sync() -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from or settings.smtp_username or ""
        msg["To"] = settings.approval_email_to or ""
        msg.attach(MIMEText(plain, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            server.starttls()
            if settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(msg["From"], [msg["To"]], msg.as_string())

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _send_sync)
        logger.info("approval_email_sent", extra={"request_id": request_id})
    except Exception:
        logger.error(
            "approval_email_send_failed",
            extra={"request_id": request_id},
            exc_info=True,
        )
