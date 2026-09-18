from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.db import get_conn


@dataclass(frozen=True)
class UserRow:
    id: int
    username: str
    password_hash: str
    email: str
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
class AssignmentRow:
    user_id: int
    username: str
    feature_id: str
    feature_title: str
    display_order: int


def _user_from_row(row: dict[str, object]) -> UserRow:
    return UserRow(
        id=int(row["id"]),
        username=str(row["username"]),
        password_hash=str(row["password_hash"]),
        email=str(row["email"]),
        is_deleted=bool(row["is_deleted"]),
    )


def _feature_from_row(row: dict[str, object]) -> FeatureRow:
    return FeatureRow(
        id=str(row["id"]),
        title=str(row["title"]),
        url=str(row["url"]),
        icon=bytes(row["icon"]),
        icon_media_type=str(row["icon_media_type"]),
        is_deleted=bool(row["is_deleted"]),
    )


def list_active_users() -> list[UserRow]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, username, password_hash, email, is_deleted
                FROM public.users
                WHERE is_deleted = false
                ORDER BY username
                """
            )
            return [_user_from_row(row) for row in cur.fetchall()]


def get_user_by_username(username: str) -> UserRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, username, password_hash, email, is_deleted
                FROM public.users
                WHERE username = %s
                """,
                (username,),
            )
            row = cur.fetchone()
            return _user_from_row(row) if row else None


def get_user_by_id(user_id: int) -> UserRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, username, password_hash, email, is_deleted
                FROM public.users
                WHERE id = %s
                """,
                (user_id,),
            )
            row = cur.fetchone()
            return _user_from_row(row) if row else None


def insert_user(username: str, password_hash: str, email: str = "") -> UserRow:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.users (username, password_hash, email)
                VALUES (%s, %s, %s)
                RETURNING id, username, password_hash, email, is_deleted
                """,
                (username, password_hash, email),
            )
            row = cur.fetchone()
            assert row is not None
            return _user_from_row(row)


def update_user(user_id: int, username: str, email: str, password_hash: str | None) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            if password_hash is None:
                cur.execute(
                    """
                    UPDATE public.users
                    SET username = %s, email = %s
                    WHERE id = %s AND is_deleted = false
                    """,
                    (username, email, user_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE public.users
                    SET username = %s, email = %s, password_hash = %s
                    WHERE id = %s AND is_deleted = false
                    """,
                    (username, email, password_hash, user_id),
                )


def logical_delete_user(user_id: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM public.sessions WHERE user_id = %s",
                (user_id,),
            )
            cur.execute(
                "UPDATE public.users SET is_deleted = true WHERE id = %s",
                (user_id,),
            )


def insert_session(session_id: UUID, user_id: int, expires_at: datetime) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM public.sessions WHERE user_id = %s",
                (user_id,),
            )
            cur.execute(
                """
                INSERT INTO public.sessions (id, user_id, expires_at)
                VALUES (%s, %s, %s)
                """,
                (str(session_id), user_id, expires_at),
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


def list_active_features() -> list[FeatureRow]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, url, icon, icon_media_type, is_deleted
                FROM public.features
                WHERE is_deleted = false
                ORDER BY id
                """
            )
            return [_feature_from_row(row) for row in cur.fetchall()]


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
            return _feature_from_row(row)


def insert_feature(
    feature_id: str,
    title: str,
    url: str,
    icon: bytes,
    icon_media_type: str,
) -> FeatureRow:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.features (id, title, url, icon, icon_media_type)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, title, url, icon, icon_media_type, is_deleted
                """,
                (feature_id, title, url, icon, icon_media_type),
            )
            row = cur.fetchone()
            assert row is not None
            return _feature_from_row(row)


def update_feature(
    feature_id: str,
    title: str,
    url: str,
    icon: bytes | None,
    icon_media_type: str | None,
) -> None:
    current = get_feature(feature_id)
    if current is None:
        return
    new_icon = icon if icon is not None else current.icon
    new_type = icon_media_type if icon_media_type is not None else current.icon_media_type
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.features
                SET title = %s, url = %s, icon = %s, icon_media_type = %s
                WHERE id = %s AND is_deleted = false
                """,
                (title, url, new_icon, new_type, feature_id),
            )


def logical_delete_feature(feature_id: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE public.features SET is_deleted = true WHERE id = %s",
                (feature_id,),
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


def insert_assignment(user_id: int, feature_id: str, display_order: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.menu_assignments (user_id, feature_id, display_order)
                VALUES (%s, %s, %s)
                """,
                (user_id, feature_id, display_order),
            )


def delete_assignment(user_id: int, feature_id: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM public.menu_assignments
                WHERE user_id = %s AND feature_id = %s
                """,
                (user_id, feature_id),
            )


def list_active_assignments() -> list[AssignmentRow]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    a.user_id,
                    u.username,
                    a.feature_id,
                    f.title AS feature_title,
                    a.display_order
                FROM public.menu_assignments a
                INNER JOIN public.users u ON u.id = a.user_id
                INNER JOIN public.features f ON f.id = a.feature_id
                WHERE u.is_deleted = false
                  AND f.is_deleted = false
                ORDER BY u.username ASC, a.display_order ASC, a.feature_id ASC
                """
            )
            rows: list[AssignmentRow] = []
            for row in cur.fetchall():
                rows.append(
                    AssignmentRow(
                        user_id=int(row["user_id"]),
                        username=str(row["username"]),
                        feature_id=str(row["feature_id"]),
                        feature_title=str(row["feature_title"]),
                        display_order=int(row["display_order"]),
                    )
                )
            return rows
