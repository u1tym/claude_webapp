from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

COOKIE_NAME = "session_id"

API_KEY_PREFIX = "wak_"
API_KEY_RANDOM_BYTES = 32
API_KEY_PREFIX_LENGTH = 12


def session_expiry(timeout_minutes: int, now: datetime | None = None) -> datetime:
    base = now or datetime.now(timezone.utc)
    return base + timedelta(minutes=timeout_minutes)


def to_data_url(media_type: str, data: bytes) -> str:
    if media_type.strip() == "" or not data:
        return ""
    payload = base64.b64encode(bytes(data)).decode("ascii")
    return f"data:{media_type};base64,{payload}"


def generate_api_key() -> str:
    """キー全体（`wak_` + 32 バイトの乱数を URL 安全な Base64 にした 43 文字）を生成する。"""
    return API_KEY_PREFIX + secrets.token_urlsafe(API_KEY_RANDOM_BYTES)


def hash_api_key(key: str) -> str:
    """キー全体の SHA-256（16 進小文字 64 文字）。保存と照合に使う。"""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def api_key_prefix(key: str) -> str:
    """識別用の先頭部分（先頭 12 文字）。"""
    return key[:API_KEY_PREFIX_LENGTH]
