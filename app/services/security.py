from __future__ import annotations

import hashlib

from app.core.config import settings


def hash_pin(pin: str) -> str:
    digest = hashlib.sha256(f"{settings.secret_key}:{pin}".encode("utf-8")).hexdigest()
    return f"sha256${digest}"


def verify_pin_hash(stored: str | None, plain_pin: str) -> bool:
    if not stored:
        return False
    if stored.startswith("sha256$"):
        return stored == hash_pin(plain_pin)
    return stored == plain_pin
