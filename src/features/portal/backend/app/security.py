from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import bcrypt
from fastapi import Response

COOKIE_NAME = "session_id"


def hash_password(password: str) -> str:
    hashed: bytes = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def new_session_id() -> UUID:
    return uuid4()


def session_expiry(timeout_minutes: int, now: datetime | None = None) -> datetime:
    base = now or datetime.now(timezone.utc)
    return base + timedelta(minutes=timeout_minutes)


def to_data_url(media_type: str, data: bytes) -> str:
    if media_type.strip() == "" or not data:
        return ""
    payload = base64.b64encode(bytes(data)).decode("ascii")
    return f"data:{media_type};base64,{payload}"


def set_session_cookie(
    response: Response,
    session_id: UUID,
    timeout_minutes: int,
    *,
    secure: bool,
) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=str(session_id),
        httponly=True,
        samesite="lax",
        secure=secure,
        max_age=timeout_minutes * 60,
        path="/",
    )


def clear_session_cookie(response: Response, *, secure: bool) -> None:
    response.delete_cookie(key=COOKIE_NAME, path="/", samesite="lax", secure=secure)
