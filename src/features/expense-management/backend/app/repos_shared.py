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
class FeatureRow:
    id: str
    title: str
    url: str
    is_deleted: bool


@dataclass(frozen=True)
class SettingRow:
    key: str
    value_text: str | None
    value_bytes: bytes | None
    value_media_type: str | None


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


def get_feature(feature_id: str) -> FeatureRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, url, is_deleted
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
                is_deleted=bool(row["is_deleted"]),
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
            return SettingRow(
                key=str(row["key"]),
                value_text=(None if row["value_text"] is None else str(row["value_text"])),
                value_bytes=(None if row["value_bytes"] is None else bytes(row["value_bytes"])),
                value_media_type=(
                    None if row["value_media_type"] is None else str(row["value_media_type"])
                ),
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
