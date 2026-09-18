from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone

import bcrypt

COOKIE_NAME = "session_id"
DATA_URL_PREFIX = "data:"


def hash_password(password: str) -> str:
    hashed: bytes = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def session_expiry(timeout_minutes: int, now: datetime | None = None) -> datetime:
    base = now or datetime.now(timezone.utc)
    return base + timedelta(minutes=timeout_minutes)


def to_data_url(media_type: str, data: bytes) -> str:
    if media_type.strip() == "" or not data:
        return ""
    payload = base64.b64encode(bytes(data)).decode("ascii")
    return f"data:{media_type};base64,{payload}"


def from_data_url(value: str) -> tuple[str, bytes] | None:
    if not value.startswith(DATA_URL_PREFIX) or ";base64," not in value:
        return None
    header, payload = value.split(";base64,", 1)
    media_type = header[len(DATA_URL_PREFIX) :]
    if media_type.strip() == "" or payload.strip() == "":
        return None
    try:
        raw = base64.b64decode(payload, validate=True)
    except ValueError:
        return None
    if not raw:
        return None
    return media_type, raw
