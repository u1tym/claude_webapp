from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
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
class PersonRow:
    id: int
    user_id: int
    name: str
    is_deleted: bool


@dataclass(frozen=True)
class ArtistRow:
    id: int
    user_id: int
    name: str
    is_deleted: bool


@dataclass(frozen=True)
class MediaRow:
    id: int
    user_id: int
    name: str
    is_deleted: bool


@dataclass(frozen=True)
class GoodsRow:
    id: int
    user_id: int
    media_id: int
    artist_id: int
    title: str
    release_date: date
    memo: str | None
    is_owned: bool
    code_number: str | None
    is_deleted: bool


@dataclass(frozen=True)
class GoodsImageRow:
    id: int
    user_id: int
    goods_id: int
    image_data: bytes
    image_type: str
    display_order: int


@dataclass(frozen=True)
class GoodsListItemRow:
    goods_id: int
    media_id: int
    media_name: str
    artist_id: int
    artist_name: str
    title: str
    release_date: date
    is_owned: bool
    code_number: str | None
    thumbnail_image_type: str | None
    thumbnail_image_data: bytes | None


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


# ---- persons ----------------------------------------------------------------


def _person_from_row(row: dict[str, object]) -> PersonRow:
    return PersonRow(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        name=str(row["name"]),
        is_deleted=bool(row["is_deleted"]),
    )


def list_persons(user_id: int) -> list[PersonRow]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, name, is_deleted
                FROM goods_management.persons
                WHERE user_id = %s AND is_deleted = false
                ORDER BY id ASC
                """,
                (user_id,),
            )
            return [_person_from_row(row) for row in cur.fetchall()]


def get_person(user_id: int, person_id: int) -> PersonRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, name, is_deleted
                FROM goods_management.persons
                WHERE id = %s AND user_id = %s AND is_deleted = false
                """,
                (person_id, user_id),
            )
            row = cur.fetchone()
            return None if row is None else _person_from_row(row)


def persons_exist(user_id: int, person_ids: list[int]) -> bool:
    if not person_ids:
        return True
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM goods_management.persons
                WHERE user_id = %s AND is_deleted = false AND id = ANY(%s)
                """,
                (user_id, list(set(person_ids))),
            )
            row = cur.fetchone()
            return int(row["cnt"]) == len(set(person_ids))


def insert_person(user_id: int, name: str) -> PersonRow:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO goods_management.persons (user_id, name)
                VALUES (%s, %s)
                RETURNING id, user_id, name, is_deleted
                """,
                (user_id, name),
            )
            row = cur.fetchone()
            assert row is not None
            return _person_from_row(row)


def update_person_name(person_id: int, user_id: int, name: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE goods_management.persons
                SET name = %s
                WHERE id = %s AND user_id = %s AND is_deleted = false
                """,
                (name, person_id, user_id),
            )


def person_referenced(user_id: int, person_id: int) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM goods_management.artist_persons ap
                JOIN goods_management.artists a ON a.id = ap.artist_id
                WHERE ap.person_id = %s AND ap.user_id = %s AND a.is_deleted = false
                LIMIT 1
                """,
                (person_id, user_id),
            )
            return cur.fetchone() is not None


def logical_delete_person(person_id: int, user_id: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE goods_management.persons
                SET is_deleted = true
                WHERE id = %s AND user_id = %s
                """,
                (person_id, user_id),
            )


# ---- artists ------------------------------------------------------------------


def _artist_from_row(row: dict[str, object]) -> ArtistRow:
    return ArtistRow(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        name=str(row["name"]),
        is_deleted=bool(row["is_deleted"]),
    )


def list_artists(user_id: int) -> list[ArtistRow]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, name, is_deleted
                FROM goods_management.artists
                WHERE user_id = %s AND is_deleted = false
                ORDER BY id ASC
                """,
                (user_id,),
            )
            return [_artist_from_row(row) for row in cur.fetchall()]


def get_artist(user_id: int, artist_id: int) -> ArtistRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, name, is_deleted
                FROM goods_management.artists
                WHERE id = %s AND user_id = %s AND is_deleted = false
                """,
                (artist_id, user_id),
            )
            row = cur.fetchone()
            return None if row is None else _artist_from_row(row)


def insert_artist(user_id: int, name: str) -> ArtistRow:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO goods_management.artists (user_id, name)
                VALUES (%s, %s)
                RETURNING id, user_id, name, is_deleted
                """,
                (user_id, name),
            )
            row = cur.fetchone()
            assert row is not None
            return _artist_from_row(row)


def update_artist_name(artist_id: int, user_id: int, name: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE goods_management.artists
                SET name = %s
                WHERE id = %s AND user_id = %s AND is_deleted = false
                """,
                (name, artist_id, user_id),
            )


def artist_referenced(user_id: int, artist_id: int) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM goods_management.goods
                WHERE artist_id = %s AND user_id = %s AND is_deleted = false
                LIMIT 1
                """,
                (artist_id, user_id),
            )
            return cur.fetchone() is not None


def logical_delete_artist(artist_id: int, user_id: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE goods_management.artists
                SET is_deleted = true
                WHERE id = %s AND user_id = %s
                """,
                (artist_id, user_id),
            )


def list_artist_person_ids(artist_id: int) -> list[int]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT person_id
                FROM goods_management.artist_persons
                WHERE artist_id = %s
                ORDER BY person_id ASC
                """,
                (artist_id,),
            )
            return [int(row["person_id"]) for row in cur.fetchall()]


def list_persons_by_ids(user_id: int, person_ids: list[int]) -> list[PersonRow]:
    if not person_ids:
        return []
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, name, is_deleted
                FROM goods_management.persons
                WHERE user_id = %s AND is_deleted = false AND id = ANY(%s)
                ORDER BY id ASC
                """,
                (user_id, list(person_ids)),
            )
            return [_person_from_row(row) for row in cur.fetchall()]


def set_artist_persons(user_id: int, artist_id: int, person_ids: list[int]) -> None:
    desired = set(person_ids)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT person_id
                FROM goods_management.artist_persons
                WHERE artist_id = %s
                """,
                (artist_id,),
            )
            current = {int(row["person_id"]) for row in cur.fetchall()}
            to_add = desired - current
            to_remove = current - desired
            for person_id in to_add:
                cur.execute(
                    """
                    INSERT INTO goods_management.artist_persons (user_id, artist_id, person_id)
                    VALUES (%s, %s, %s)
                    """,
                    (user_id, artist_id, person_id),
                )
            if to_remove:
                cur.execute(
                    """
                    DELETE FROM goods_management.artist_persons
                    WHERE artist_id = %s AND person_id = ANY(%s)
                    """,
                    (artist_id, list(to_remove)),
                )


# ---- media --------------------------------------------------------------------


def _media_from_row(row: dict[str, object]) -> MediaRow:
    return MediaRow(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        name=str(row["name"]),
        is_deleted=bool(row["is_deleted"]),
    )


def list_media(user_id: int) -> list[MediaRow]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, name, is_deleted
                FROM goods_management.media
                WHERE user_id = %s AND is_deleted = false
                ORDER BY id ASC
                """,
                (user_id,),
            )
            return [_media_from_row(row) for row in cur.fetchall()]


def get_media(user_id: int, media_id: int) -> MediaRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, name, is_deleted
                FROM goods_management.media
                WHERE id = %s AND user_id = %s AND is_deleted = false
                """,
                (media_id, user_id),
            )
            row = cur.fetchone()
            return None if row is None else _media_from_row(row)


def insert_media(user_id: int, name: str) -> MediaRow:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO goods_management.media (user_id, name)
                VALUES (%s, %s)
                RETURNING id, user_id, name, is_deleted
                """,
                (user_id, name),
            )
            row = cur.fetchone()
            assert row is not None
            return _media_from_row(row)


def update_media_name(media_id: int, user_id: int, name: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE goods_management.media
                SET name = %s
                WHERE id = %s AND user_id = %s AND is_deleted = false
                """,
                (name, media_id, user_id),
            )


def media_referenced(user_id: int, media_id: int) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM goods_management.goods
                WHERE media_id = %s AND user_id = %s AND is_deleted = false
                LIMIT 1
                """,
                (media_id, user_id),
            )
            return cur.fetchone() is not None


def logical_delete_media(media_id: int, user_id: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE goods_management.media
                SET is_deleted = true
                WHERE id = %s AND user_id = %s
                """,
                (media_id, user_id),
            )


# ---- goods relations (person -> artists / media) -------------------------------


def related_artists_by_person(user_id: int, person_id: int) -> list[ArtistRow]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.id, a.user_id, a.name, a.is_deleted
                FROM goods_management.artist_persons ap
                JOIN goods_management.artists a ON a.id = ap.artist_id
                WHERE ap.person_id = %s AND ap.user_id = %s AND a.is_deleted = false
                ORDER BY a.id ASC
                """,
                (person_id, user_id),
            )
            return [_artist_from_row(row) for row in cur.fetchall()]


def related_artist_ids_by_person(user_id: int, person_id: int) -> list[int]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ap.artist_id
                FROM goods_management.artist_persons ap
                JOIN goods_management.artists a ON a.id = ap.artist_id
                WHERE ap.person_id = %s AND ap.user_id = %s AND a.is_deleted = false
                """,
                (person_id, user_id),
            )
            return [int(row["artist_id"]) for row in cur.fetchall()]


def related_media_by_person(user_id: int, person_id: int) -> list[MediaRow]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT m.id, m.user_id, m.name, m.is_deleted
                FROM goods_management.artist_persons ap
                JOIN goods_management.goods g ON g.artist_id = ap.artist_id
                JOIN goods_management.media m ON m.id = g.media_id
                WHERE ap.person_id = %s AND ap.user_id = %s
                    AND g.user_id = %s AND g.is_deleted = false AND m.is_deleted = false
                ORDER BY m.id ASC
                """,
                (person_id, user_id, user_id),
            )
            return [_media_from_row(row) for row in cur.fetchall()]


# ---- goods ----------------------------------------------------------------------


def _goods_from_row(row: dict[str, object]) -> GoodsRow:
    return GoodsRow(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        media_id=int(row["media_id"]),
        artist_id=int(row["artist_id"]),
        title=str(row["title"]),
        release_date=row["release_date"],
        memo=(None if row["memo"] is None else str(row["memo"])),
        is_owned=bool(row["is_owned"]),
        code_number=(None if row["code_number"] is None else str(row["code_number"])),
        is_deleted=bool(row["is_deleted"]),
    )


def get_goods(user_id: int, goods_id: int) -> GoodsRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, media_id, artist_id, title, release_date, memo,
                       is_owned, code_number, is_deleted
                FROM goods_management.goods
                WHERE id = %s AND user_id = %s AND is_deleted = false
                """,
                (goods_id, user_id),
            )
            row = cur.fetchone()
            return None if row is None else _goods_from_row(row)


def insert_goods(
    user_id: int,
    media_id: int,
    artist_id: int,
    title: str,
    release_date: date,
    memo: str | None,
    is_owned: bool,
    code_number: str | None,
) -> GoodsRow:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO goods_management.goods
                    (user_id, media_id, artist_id, title, release_date, memo, is_owned, code_number)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, user_id, media_id, artist_id, title, release_date, memo,
                          is_owned, code_number, is_deleted
                """,
                (user_id, media_id, artist_id, title, release_date, memo, is_owned, code_number),
            )
            row = cur.fetchone()
            assert row is not None
            return _goods_from_row(row)


def update_goods(
    goods_id: int,
    user_id: int,
    media_id: int,
    artist_id: int,
    title: str,
    release_date: date | None,
    memo: str | None,
    is_owned: bool,
    code_number: str | None,
) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            if release_date is None:
                cur.execute(
                    """
                    UPDATE goods_management.goods
                    SET media_id = %s, artist_id = %s, title = %s, memo = %s,
                        is_owned = %s, code_number = %s
                    WHERE id = %s AND user_id = %s AND is_deleted = false
                    """,
                    (media_id, artist_id, title, memo, is_owned, code_number, goods_id, user_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE goods_management.goods
                    SET media_id = %s, artist_id = %s, title = %s, release_date = %s, memo = %s,
                        is_owned = %s, code_number = %s
                    WHERE id = %s AND user_id = %s AND is_deleted = false
                    """,
                    (
                        media_id,
                        artist_id,
                        title,
                        release_date,
                        memo,
                        is_owned,
                        code_number,
                        goods_id,
                        user_id,
                    ),
                )


def logical_delete_goods(goods_id: int, user_id: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE goods_management.goods
                SET is_deleted = true
                WHERE id = %s AND user_id = %s
                """,
                (goods_id, user_id),
            )


def list_goods(
    user_id: int,
    artist_ids: list[int],
    media_id: int | None,
) -> list[GoodsListItemRow]:
    if not artist_ids:
        return []
    params: list[object] = [user_id, list(artist_ids)]
    media_clause = ""
    if media_id is not None:
        media_clause = "AND g.media_id = %s"
        params.append(media_id)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    g.id AS goods_id,
                    g.media_id AS media_id,
                    m.name AS media_name,
                    g.artist_id AS artist_id,
                    a.name AS artist_name,
                    g.title AS title,
                    g.release_date AS release_date,
                    g.is_owned AS is_owned,
                    g.code_number AS code_number,
                    thumb.image_type AS thumbnail_image_type,
                    thumb.image_data AS thumbnail_image_data
                FROM goods_management.goods g
                JOIN goods_management.media m ON m.id = g.media_id
                JOIN goods_management.artists a ON a.id = g.artist_id
                LEFT JOIN LATERAL (
                    SELECT gi.image_type, gi.image_data
                    FROM goods_management.goods_images gi
                    WHERE gi.goods_id = g.id
                    ORDER BY gi.display_order ASC
                    LIMIT 1
                ) thumb ON true
                WHERE g.user_id = %s AND g.is_deleted = false AND g.artist_id = ANY(%s) {media_clause}
                ORDER BY g.release_date DESC, g.id DESC
                """,
                params,
            )
            items: list[GoodsListItemRow] = []
            for row in cur.fetchall():
                thumb_data = row["thumbnail_image_data"]
                items.append(
                    GoodsListItemRow(
                        goods_id=int(row["goods_id"]),
                        media_id=int(row["media_id"]),
                        media_name=str(row["media_name"]),
                        artist_id=int(row["artist_id"]),
                        artist_name=str(row["artist_name"]),
                        title=str(row["title"]),
                        release_date=row["release_date"],
                        is_owned=bool(row["is_owned"]),
                        code_number=(None if row["code_number"] is None else str(row["code_number"])),
                        thumbnail_image_type=(
                            None if row["thumbnail_image_type"] is None else str(row["thumbnail_image_type"])
                        ),
                        thumbnail_image_data=(None if thumb_data is None else bytes(thumb_data)),
                    )
                )
            return items


# ---- goods images ------------------------------------------------------------------


def _goods_image_from_row(row: dict[str, object]) -> GoodsImageRow:
    return GoodsImageRow(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        goods_id=int(row["goods_id"]),
        image_data=bytes(row["image_data"]),
        image_type=str(row["image_type"]),
        display_order=int(row["display_order"]),
    )


def list_goods_images(goods_id: int) -> list[GoodsImageRow]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, goods_id, image_data, image_type, display_order
                FROM goods_management.goods_images
                WHERE goods_id = %s
                ORDER BY display_order ASC, id ASC
                """,
                (goods_id,),
            )
            return [_goods_image_from_row(row) for row in cur.fetchall()]


def insert_goods_image(
    user_id: int, goods_id: int, image_data: bytes, image_type: str
) -> GoodsImageRow:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(MAX(display_order), 0) + 1 AS next_order
                FROM goods_management.goods_images
                WHERE goods_id = %s
                """,
                (goods_id,),
            )
            next_order = cur.fetchone()["next_order"]
            cur.execute(
                """
                INSERT INTO goods_management.goods_images
                    (user_id, goods_id, image_data, image_type, display_order)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, user_id, goods_id, image_data, image_type, display_order
                """,
                (user_id, goods_id, image_data, image_type, next_order),
            )
            row = cur.fetchone()
            assert row is not None
            return _goods_image_from_row(row)


def get_goods_image(user_id: int, goods_id: int, image_id: int) -> GoodsImageRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, goods_id, image_data, image_type, display_order
                FROM goods_management.goods_images
                WHERE id = %s AND goods_id = %s AND user_id = %s
                """,
                (image_id, goods_id, user_id),
            )
            row = cur.fetchone()
            return None if row is None else _goods_image_from_row(row)


def delete_goods_image(image_id: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM goods_management.goods_images
                WHERE id = %s
                """,
                (image_id,),
            )



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
