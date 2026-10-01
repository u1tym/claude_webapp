from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timedelta, timezone

COOKIE_NAME = "session_id"

# 識別用の先頭部分の長さ（ログに出してよいのはここまで）
API_KEY_PREFIX_LENGTH = 12


def session_expiry(timeout_minutes: int, now: datetime | None = None) -> datetime:
    """セッションの有効期限（現在 + 有効期間）を返す。"""
    base = now or datetime.now(timezone.utc)
    return base + timedelta(minutes=timeout_minutes)


def to_data_url(media_type: str, data: bytes) -> str:
    """アイコンのバイナリを data URL にする。空なら空文字を返す。"""
    if media_type.strip() == "" or not data:
        return ""
    payload = base64.b64encode(bytes(data)).decode("ascii")
    return f"data:{media_type};base64,{payload}"


def hash_api_key(key: str) -> str:
    """API キー全体の SHA-256（16 進小文字 64 文字）。`public.api_keys.key_hash` と照合する。"""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def bearer_token(authorization: str) -> str | None:
    """`Authorization` ヘッダから Bearer のトークンを取り出す。Bearer でない・空なら None。"""
    scheme, _, token = authorization.strip().partition(" ")
    if scheme.lower() != "bearer":
        return None
    token = token.strip()
    return token or None
