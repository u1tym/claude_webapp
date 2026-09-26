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
class MajorCategoryRow:
    id: int
    user_id: int
    name: str
    display_order: int
    is_deleted: bool


@dataclass(frozen=True)
class MiddleCategoryRow:
    id: int
    user_id: int
    major_category_id: int
    name: str
    display_order: int
    is_deleted: bool


@dataclass(frozen=True)
class KnowhowRow:
    id: int
    user_id: int
    middle_category_id: int | None
    title: str
    keywords: str | None
    content: str
    display_order: int
    is_deleted: bool


@dataclass(frozen=True)
class KnowhowSearchRow:
    knowhow_id: int
    title: str
    display_order: int
    middle_category_id: int | None
    middle_category_name: str | None
    major_category_id: int | None
    major_category_name: str | None


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


# ---- major_categories ----------------------------------------------------


def _major_from_row(row: dict[str, object]) -> MajorCategoryRow:
    return MajorCategoryRow(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        name=str(row["name"]),
        display_order=int(row["display_order"]),
        is_deleted=bool(row["is_deleted"]),
    )


def list_major_categories(user_id: int) -> list[MajorCategoryRow]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, name, display_order, is_deleted
                FROM knowhow_management.major_categories
                WHERE user_id = %s AND is_deleted = false
                ORDER BY display_order ASC, id ASC
                """,
                (user_id,),
            )
            return [_major_from_row(row) for row in cur.fetchall()]


def get_major_category(user_id: int, major_category_id: int) -> MajorCategoryRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, name, display_order, is_deleted
                FROM knowhow_management.major_categories
                WHERE id = %s AND user_id = %s AND is_deleted = false
                """,
                (major_category_id, user_id),
            )
            row = cur.fetchone()
            return None if row is None else _major_from_row(row)


def major_category_name_exists(user_id: int, name: str, exclude_id: int | None = None) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            if exclude_id is None:
                cur.execute(
                    """
                    SELECT 1 FROM knowhow_management.major_categories
                    WHERE user_id = %s AND name = %s AND is_deleted = false
                    """,
                    (user_id, name),
                )
            else:
                cur.execute(
                    """
                    SELECT 1 FROM knowhow_management.major_categories
                    WHERE user_id = %s AND name = %s AND is_deleted = false AND id != %s
                    """,
                    (user_id, name, exclude_id),
                )
            return cur.fetchone() is not None


def insert_major_category(user_id: int, name: str) -> MajorCategoryRow:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(MAX(display_order), 0) + 1 AS next_order
                FROM knowhow_management.major_categories
                WHERE user_id = %s AND is_deleted = false
                """,
                (user_id,),
            )
            next_order = cur.fetchone()["next_order"]
            cur.execute(
                """
                INSERT INTO knowhow_management.major_categories (user_id, name, display_order)
                VALUES (%s, %s, %s)
                RETURNING id, user_id, name, display_order, is_deleted
                """,
                (user_id, name, next_order),
            )
            row = cur.fetchone()
            assert row is not None
            return _major_from_row(row)


def update_major_category_name(major_category_id: int, user_id: int, name: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE knowhow_management.major_categories
                SET name = %s
                WHERE id = %s AND user_id = %s AND is_deleted = false
                """,
                (name, major_category_id, user_id),
            )


def cascade_delete_major_category(major_category_id: int, user_id: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE knowhow_management.knowhows
                SET is_deleted = true
                WHERE user_id = %s AND is_deleted = false AND middle_category_id IN (
                    SELECT id FROM knowhow_management.middle_categories
                    WHERE major_category_id = %s AND user_id = %s
                )
                """,
                (user_id, major_category_id, user_id),
            )
            cur.execute(
                """
                UPDATE knowhow_management.middle_categories
                SET is_deleted = true
                WHERE major_category_id = %s AND user_id = %s AND is_deleted = false
                """,
                (major_category_id, user_id),
            )
            cur.execute(
                """
                UPDATE knowhow_management.major_categories
                SET is_deleted = true
                WHERE id = %s AND user_id = %s
                """,
                (major_category_id, user_id),
            )


# ---- middle_categories -----------------------------------------------------


def _middle_from_row(row: dict[str, object]) -> MiddleCategoryRow:
    return MiddleCategoryRow(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        major_category_id=int(row["major_category_id"]),
        name=str(row["name"]),
        display_order=int(row["display_order"]),
        is_deleted=bool(row["is_deleted"]),
    )


def list_middle_categories(user_id: int, major_category_id: int) -> list[MiddleCategoryRow]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, major_category_id, name, display_order, is_deleted
                FROM knowhow_management.middle_categories
                WHERE major_category_id = %s AND user_id = %s AND is_deleted = false
                ORDER BY display_order ASC, id ASC
                """,
                (major_category_id, user_id),
            )
            return [_middle_from_row(row) for row in cur.fetchall()]


def get_middle_category(user_id: int, middle_category_id: int) -> MiddleCategoryRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, major_category_id, name, display_order, is_deleted
                FROM knowhow_management.middle_categories
                WHERE id = %s AND user_id = %s AND is_deleted = false
                """,
                (middle_category_id, user_id),
            )
            row = cur.fetchone()
            return None if row is None else _middle_from_row(row)


def middle_category_name_exists(
    major_category_id: int, name: str, exclude_id: int | None = None
) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            if exclude_id is None:
                cur.execute(
                    """
                    SELECT 1 FROM knowhow_management.middle_categories
                    WHERE major_category_id = %s AND name = %s AND is_deleted = false
                    """,
                    (major_category_id, name),
                )
            else:
                cur.execute(
                    """
                    SELECT 1 FROM knowhow_management.middle_categories
                    WHERE major_category_id = %s AND name = %s AND is_deleted = false AND id != %s
                    """,
                    (major_category_id, name, exclude_id),
                )
            return cur.fetchone() is not None


def insert_middle_category(user_id: int, major_category_id: int, name: str) -> MiddleCategoryRow:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(MAX(display_order), 0) + 1 AS next_order
                FROM knowhow_management.middle_categories
                WHERE major_category_id = %s AND user_id = %s AND is_deleted = false
                """,
                (major_category_id, user_id),
            )
            next_order = cur.fetchone()["next_order"]
            cur.execute(
                """
                INSERT INTO knowhow_management.middle_categories
                    (user_id, major_category_id, name, display_order)
                VALUES (%s, %s, %s, %s)
                RETURNING id, user_id, major_category_id, name, display_order, is_deleted
                """,
                (user_id, major_category_id, name, next_order),
            )
            row = cur.fetchone()
            assert row is not None
            return _middle_from_row(row)


def update_middle_category_name(middle_category_id: int, user_id: int, name: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE knowhow_management.middle_categories
                SET name = %s
                WHERE id = %s AND user_id = %s AND is_deleted = false
                """,
                (name, middle_category_id, user_id),
            )


def cascade_delete_middle_category(middle_category_id: int, user_id: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE knowhow_management.knowhows
                SET is_deleted = true
                WHERE user_id = %s AND is_deleted = false AND middle_category_id = %s
                """,
                (user_id, middle_category_id),
            )
            cur.execute(
                """
                UPDATE knowhow_management.middle_categories
                SET is_deleted = true
                WHERE id = %s AND user_id = %s
                """,
                (middle_category_id, user_id),
            )


# ---- knowhows ---------------------------------------------------------------


def _knowhow_from_row(row: dict[str, object]) -> KnowhowRow:
    return KnowhowRow(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        middle_category_id=(None if row["middle_category_id"] is None else int(row["middle_category_id"])),
        title=str(row["title"]),
        keywords=(None if row["keywords"] is None else str(row["keywords"])),
        content=str(row["content"]),
        display_order=int(row["display_order"]),
        is_deleted=bool(row["is_deleted"]),
    )


def list_knowhows_by_middle(user_id: int, middle_category_id: int) -> list[KnowhowRow]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, middle_category_id, title, keywords, content, display_order, is_deleted
                FROM knowhow_management.knowhows
                WHERE user_id = %s AND middle_category_id = %s AND is_deleted = false
                ORDER BY display_order ASC, id ASC
                """,
                (user_id, middle_category_id),
            )
            return [_knowhow_from_row(row) for row in cur.fetchall()]


def get_knowhow(user_id: int, knowhow_id: int) -> KnowhowRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, middle_category_id, title, keywords, content, display_order, is_deleted
                FROM knowhow_management.knowhows
                WHERE id = %s AND user_id = %s AND is_deleted = false
                """,
                (knowhow_id, user_id),
            )
            row = cur.fetchone()
            return None if row is None else _knowhow_from_row(row)


def next_knowhow_display_order(user_id: int, middle_category_id: int | None) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            if middle_category_id is None:
                cur.execute(
                    """
                    SELECT COALESCE(MAX(display_order), 0) + 1 AS next_order
                    FROM knowhow_management.knowhows
                    WHERE user_id = %s AND middle_category_id IS NULL AND is_deleted = false
                    """,
                    (user_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT COALESCE(MAX(display_order), 0) + 1 AS next_order
                    FROM knowhow_management.knowhows
                    WHERE user_id = %s AND middle_category_id = %s AND is_deleted = false
                    """,
                    (user_id, middle_category_id),
                )
            return int(cur.fetchone()["next_order"])


def insert_knowhow(
    user_id: int,
    middle_category_id: int | None,
    title: str,
    keywords: str | None,
    content: str,
    display_order: int,
) -> KnowhowRow:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO knowhow_management.knowhows
                    (user_id, middle_category_id, title, keywords, content, display_order)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, user_id, middle_category_id, title, keywords, content, display_order, is_deleted
                """,
                (user_id, middle_category_id, title, keywords, content, display_order),
            )
            row = cur.fetchone()
            assert row is not None
            return _knowhow_from_row(row)


def update_knowhow(
    knowhow_id: int,
    user_id: int,
    middle_category_id: int | None,
    title: str,
    keywords: str | None,
    content: str,
    display_order: int,
) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE knowhow_management.knowhows
                SET middle_category_id = %s, title = %s, keywords = %s, content = %s, display_order = %s
                WHERE id = %s AND user_id = %s AND is_deleted = false
                """,
                (middle_category_id, title, keywords, content, display_order, knowhow_id, user_id),
            )


def logical_delete_knowhow(knowhow_id: int, user_id: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE knowhow_management.knowhows
                SET is_deleted = true
                WHERE id = %s AND user_id = %s
                """,
                (knowhow_id, user_id),
            )


def set_knowhow_display_order(knowhow_id: int, user_id: int, display_order: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE knowhow_management.knowhows
                SET display_order = %s
                WHERE id = %s AND user_id = %s
                """,
                (display_order, knowhow_id, user_id),
            )


def search_knowhows(user_id: int, keywords: list[str]) -> list[KnowhowSearchRow]:
    conditions = []
    params: list[object] = [user_id]
    for keyword in keywords:
        like_pattern = f"%{keyword}%"
        conditions.append(
            "(k.title ILIKE %s OR k.keywords ILIKE %s OR k.content ILIKE %s)"
        )
        params.extend([like_pattern, like_pattern, like_pattern])
    where_clause = " AND ".join(conditions)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    k.id AS knowhow_id,
                    k.title AS title,
                    k.display_order AS display_order,
                    mc.id AS middle_category_id,
                    mc.name AS middle_category_name,
                    majc.id AS major_category_id,
                    majc.name AS major_category_name
                FROM knowhow_management.knowhows k
                LEFT JOIN knowhow_management.middle_categories mc ON mc.id = k.middle_category_id
                LEFT JOIN knowhow_management.major_categories majc ON majc.id = mc.major_category_id
                WHERE k.user_id = %s AND k.is_deleted = false AND {where_clause}
                ORDER BY k.id ASC
                """,
                params,
            )
            return [
                KnowhowSearchRow(
                    knowhow_id=int(row["knowhow_id"]),
                    title=str(row["title"]),
                    display_order=int(row["display_order"]),
                    middle_category_id=(
                        None if row["middle_category_id"] is None else int(row["middle_category_id"])
                    ),
                    middle_category_name=(
                        None if row["middle_category_name"] is None else str(row["middle_category_name"])
                    ),
                    major_category_id=(
                        None if row["major_category_id"] is None else int(row["major_category_id"])
                    ),
                    major_category_name=(
                        None if row["major_category_name"] is None else str(row["major_category_name"])
                    ),
                )
                for row in cur.fetchall()
            ]



# ---- api_keys（api-key-management が作成する。読み取りと last_used_at の更新だけ行う） ----


@dataclass(frozen=True)
class ApiKeyAuthRow:
    id: int
    user_id: int
    key_prefix: str
    expires_at: datetime | None
    revoked_at: datetime | None
    username: str
    user_is_deleted: bool


def find_api_key_by_hash(key_hash: str) -> ApiKeyAuthRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT k.id, k.user_id, k.key_prefix, k.expires_at, k.revoked_at,
                       u.username, u.is_deleted
                FROM public.api_keys k
                JOIN public.users u ON u.id = k.user_id
                WHERE k.key_hash = %s
                """,
                (key_hash,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return ApiKeyAuthRow(
                id=int(row["id"]),
                user_id=int(row["user_id"]),
                key_prefix=str(row["key_prefix"]),
                expires_at=row["expires_at"],
                revoked_at=row["revoked_at"],
                username=str(row["username"]),
                user_is_deleted=bool(row["is_deleted"]),
            )


def touch_api_key_last_used(api_key_id: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE public.api_keys SET last_used_at = now() WHERE id = %s",
                (api_key_id,),
            )
