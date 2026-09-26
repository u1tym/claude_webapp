from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from psycopg2.errors import UniqueViolation

from app.errors import AlreadyRevokedError, InvalidInputError, NotFoundError
from app.repos import ApiKeyRow, get_api_key, insert_api_key, list_api_keys, revoke_api_key
from app.security import api_key_prefix, generate_api_key, hash_api_key

NAME_MAX_LENGTH = 100
_MAX_GENERATE_ATTEMPTS = 5


@dataclass(frozen=True)
class IssuedApiKey:
    row: ApiKeyRow
    key: str


def status_of(row: ApiKeyRow, now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    if row.revoked_at is not None:
        return "revoked"
    if row.expires_at is not None and row.expires_at <= current:
        return "expired"
    return "active"


def normalize_name(name: str) -> str:
    stripped = name.strip()
    if stripped == "" or len(stripped) > NAME_MAX_LENGTH:
        raise InvalidInputError("名前が空または長すぎる")
    return stripped


def validate_expires_at(expires_at: datetime | None) -> datetime | None:
    if expires_at is None:
        return None
    if expires_at.tzinfo is None:
        raise InvalidInputError("有効期限にタイムゾーンがない")
    if expires_at <= datetime.now(timezone.utc):
        raise InvalidInputError("有効期限が現在以前")
    return expires_at


def issue(user_id: int, name: str, expires_at: datetime | None) -> IssuedApiKey:
    normalized = normalize_name(name)
    expiry = validate_expires_at(expires_at)
    for _ in range(_MAX_GENERATE_ATTEMPTS):
        key = generate_api_key()
        try:
            row = insert_api_key(user_id, normalized, hash_api_key(key), api_key_prefix(key), expiry)
        except UniqueViolation:
            continue
        return IssuedApiKey(row=row, key=key)
    raise RuntimeError("API キーの生成が重複し続けた")


def list_for_user(user_id: int) -> list[ApiKeyRow]:
    return list_api_keys(user_id)


def revoke(user_id: int, api_key_id: int) -> ApiKeyRow:
    revoked = revoke_api_key(user_id, api_key_id)
    if revoked is not None:
        return revoked
    existing = get_api_key(user_id, api_key_id)
    if existing is None:
        raise NotFoundError("対象なし")
    raise AlreadyRevokedError("失効済み")
