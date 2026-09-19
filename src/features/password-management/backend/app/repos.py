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
class EntryRow:
    id: int
    user_id: int
    title: str
    userword: str
    psword: str
    site: str | None
    memo: str | None
    is_deleted: bool


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


def _entry_from_row(row: dict[str, object]) -> EntryRow:
    return EntryRow(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        title=str(row["title"]),
        userword=str(row["userword"]),
        psword=str(row["psword"]),
        site=(None if row["site"] is None else str(row["site"])),
        memo=(None if row["memo"] is None else str(row["memo"])),
        is_deleted=bool(row["is_deleted"]),
    )


def list_entries(user_id: int) -> list[EntryRow]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, title, userword, psword, site, memo, is_deleted
                FROM password_management.entries
                WHERE user_id = %s AND is_deleted = false
                ORDER BY id ASC
                """,
                (user_id,),
            )
            return [_entry_from_row(row) for row in cur.fetchall()]


def search_entries(user_id: int, keyword: str) -> list[EntryRow]:
    like_pattern = f"%{keyword}%"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, title, userword, psword, site, memo, is_deleted
                FROM password_management.entries
                WHERE user_id = %s AND is_deleted = false
                  AND (
                    title ILIKE %s
                    OR userword ILIKE %s
                    OR site ILIKE %s
                    OR memo ILIKE %s
                  )
                ORDER BY id ASC
                """,
                (user_id, like_pattern, like_pattern, like_pattern, like_pattern),
            )
            return [_entry_from_row(row) for row in cur.fetchall()]


def get_entry(user_id: int, entry_id: int) -> EntryRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, title, userword, psword, site, memo, is_deleted
                FROM password_management.entries
                WHERE id = %s AND user_id = %s AND is_deleted = false
                """,
                (entry_id, user_id),
            )
            row = cur.fetchone()
            return None if row is None else _entry_from_row(row)


def title_exists(user_id: int, title: str, exclude_id: int | None = None) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            if exclude_id is None:
                cur.execute(
                    """
                    SELECT 1
                    FROM password_management.entries
                    WHERE user_id = %s AND title = %s AND is_deleted = false
                    """,
                    (user_id, title),
                )
            else:
                cur.execute(
                    """
                    SELECT 1
                    FROM password_management.entries
                    WHERE user_id = %s AND title = %s AND is_deleted = false AND id != %s
                    """,
                    (user_id, title, exclude_id),
                )
            return cur.fetchone() is not None


def insert_entry(
    user_id: int,
    title: str,
    userword: str,
    psword: str,
    site: str | None,
    memo: str | None,
) -> EntryRow:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO password_management.entries
                    (user_id, title, userword, psword, site, memo)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, user_id, title, userword, psword, site, memo, is_deleted
                """,
                (user_id, title, userword, psword, site, memo),
            )
            row = cur.fetchone()
            assert row is not None
            return _entry_from_row(row)


def update_entry(
    entry_id: int,
    user_id: int,
    title: str,
    userword: str,
    psword: str,
    site: str | None,
    memo: str | None,
) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE password_management.entries
                SET title = %s, userword = %s, psword = %s, site = %s, memo = %s
                WHERE id = %s AND user_id = %s AND is_deleted = false
                """,
                (title, userword, psword, site, memo, entry_id, user_id),
            )


def logical_delete_entry(entry_id: int, user_id: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE password_management.entries
                SET is_deleted = true
                WHERE id = %s AND user_id = %s
                """,
                (entry_id, user_id),
            )
