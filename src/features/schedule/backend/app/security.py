from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone

COOKIE_NAME = "session_id"
DATA_URL_PREFIX = "data:"


def session_expiry(timeout_minutes: int, now: datetime | None = None) -> datetime:
    base = now or datetime.now(timezone.utc)
    return base + timedelta(minutes=timeout_minutes)


def to_data_url(media_type: str, data: bytes) -> str:
    if media_type.strip() == "" or not data:
        return ""
    payload = base64.b64encode(bytes(data)).decode("ascii")
    return f"data:{media_type};base64,{payload}"
