from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.db import get_conn


@dataclass(frozen=True)
class UserRow:
    id: int
    username: str
    is_deleted: bool


@dataclass(frozen=True)
class SessionRow:
    id: UUID
    user_id: int
    expires_at: datetime


@dataclass(frozen=True)
class SettingRow:
    key: str
    value_text: str | None
    value_bytes: bytes | None
    value_media_type: str | None


@dataclass(frozen=True)
class FeatureRow:
    id: str
    title: str
    url: str
    icon: bytes
    icon_media_type: str
    is_deleted: bool


@dataclass(frozen=True)
class ApiKeyRow:
    id: int
    user_id: int
    name: str
    key_prefix: str
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None


def get_user_by_username(username: str) -> UserRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, username, is_deleted
                FROM public.users
                WHERE username = %s
                """,
                (username,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return UserRow(
                id=int(row["id"]),
                username=str(row["username"]),
                is_deleted=bool(row["is_deleted"]),
            )


def get_user_by_id(user_id: int) -> UserRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, username, is_deleted
                FROM public.users
                WHERE id = %s
                """,
                (user_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return UserRow(
                id=int(row["id"]),
                username=str(row["username"]),
                is_deleted=bool(row["is_deleted"]),
            )


def get_session(session_id: UUID) -> SessionRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, expires_at
                FROM public.sessions
                WHERE id = %s
                """,
                (str(session_id),),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return SessionRow(
                id=UUID(str(row["id"])),
                user_id=int(row["user_id"]),
                expires_at=row["expires_at"],
            )


def update_session_expiry(session_id: UUID, expires_at: datetime) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.sessions
                SET expires_at = %s
                WHERE id = %s
                """,
                (expires_at, str(session_id)),
            )


def get_setting(key: str) -> SettingRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT key, value_text, value_bytes, value_media_type
                FROM public.system_settings
                WHERE key = %s
                """,
                (key,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            raw_bytes = row["value_bytes"]
            return SettingRow(
                key=str(row["key"]),
                value_text=str(row["value_text"]) if row["value_text"] is not None else None,
                value_bytes=bytes(raw_bytes) if raw_bytes is not None else None,
                value_media_type=(
                    str(row["value_media_type"]) if row["value_media_type"] is not None else None
                ),
            )


def get_feature(feature_id: str) -> FeatureRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, url, icon, icon_media_type, is_deleted
                FROM public.features
                WHERE id = %s
                """,
                (feature_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return FeatureRow(
                id=str(row["id"]),
                title=str(row["title"]),
                url=str(row["url"]),
                icon=bytes(row["icon"]),
                icon_media_type=str(row["icon_media_type"]),
                is_deleted=bool(row["is_deleted"]),
            )


def assignment_exists(user_id: int, feature_id: str) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM public.menu_assignments
                WHERE user_id = %s AND feature_id = %s
                """,
                (user_id, feature_id),
            )
            return cur.fetchone() is not None


# ---- api_keys ------------------------------------------------------------

_API_KEY_COLUMNS = (
    "id, user_id, name, key_prefix, created_at, expires_at, last_used_at, revoked_at"
)


def _api_key_from_row(row: dict[str, object]) -> ApiKeyRow:
    return ApiKeyRow(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        name=str(row["name"]),
        key_prefix=str(row["key_prefix"]),
        created_at=row["created_at"],
        expires_at=row["expires_at"],
        last_used_at=row["last_used_at"],
        revoked_at=row["revoked_at"],
    )


def insert_api_key(
    user_id: int,
    name: str,
    key_hash: str,
    key_prefix: str,
    expires_at: datetime | None,
) -> ApiKeyRow:
    """挿入する。`key_hash` の重複は psycopg2.errors.UniqueViolation を送出する。"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO public.api_keys (user_id, name, key_hash, key_prefix, expires_at)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING {_API_KEY_COLUMNS}
                """,
                (user_id, name, key_hash, key_prefix, expires_at),
            )
            row = cur.fetchone()
            assert row is not None
            return _api_key_from_row(row)


def list_api_keys(user_id: int) -> list[ApiKeyRow]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {_API_KEY_COLUMNS}
                FROM public.api_keys
                WHERE user_id = %s
                ORDER BY created_at DESC, id DESC
                """,
                (user_id,),
            )
            return [_api_key_from_row(row) for row in cur.fetchall()]


def get_api_key(user_id: int, api_key_id: int) -> ApiKeyRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {_API_KEY_COLUMNS}
                FROM public.api_keys
                WHERE id = %s AND user_id = %s
                """,
                (api_key_id, user_id),
            )
            row = cur.fetchone()
            return _api_key_from_row(row) if row is not None else None


def revoke_api_key(user_id: int, api_key_id: int) -> ApiKeyRow | None:
    """本人の未失効の行だけ失効させる。対象が無ければ None。"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE public.api_keys
                SET revoked_at = now()
                WHERE id = %s AND user_id = %s AND revoked_at IS NULL
                RETURNING {_API_KEY_COLUMNS}
                """,
                (api_key_id, user_id),
            )
            row = cur.fetchone()
            return _api_key_from_row(row) if row is not None else None
