from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from psycopg2.extensions import cursor as PgCursor
from psycopg2.extras import execute_values

_COLUMNS = "id, name, description, created_at, updated_at"


def count_playlists(cur: PgCursor, user_id: int) -> int:
    cur.execute("SELECT count(*) AS n FROM movie_management.playlists WHERE user_id = %s", (user_id,))
    return int(cur.fetchone()["n"])


def list_playlists(cur: PgCursor, user_id: int, limit: int, offset: int) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT p.id, p.name, p.description,
               (SELECT count(*) FROM movie_management.playlist_items i WHERE i.playlist_id = p.id) AS item_count,
               p.created_at, p.updated_at
        FROM movie_management.playlists p
        WHERE p.user_id = %s
        ORDER BY p.updated_at DESC, p.id DESC
        LIMIT %s OFFSET %s
        """,
        (user_id, limit, offset),
    )
    return [dict(row) for row in cur.fetchall()]


def insert_playlist(cur: PgCursor, user_id: int, name: str, description: str | None) -> dict[str, Any]:
    cur.execute(
        f"""
        INSERT INTO movie_management.playlists (user_id, name, description)
        VALUES (%s, %s, %s)
        RETURNING {_COLUMNS}
        """,
        (user_id, name, description),
    )
    return dict(cur.fetchone())


def get_playlist(cur: PgCursor, user_id: int, playlist_id: int, *, lock: bool = False) -> dict[str, Any] | None:
    cur.execute(
        f"""
        SELECT {_COLUMNS} FROM movie_management.playlists
        WHERE id = %s AND user_id = %s
        {"FOR UPDATE" if lock else ""}
        """,
        (playlist_id, user_id),
    )
    row = cur.fetchone()
    return dict(row) if row is not None else None


def list_items(cur: PgCursor, playlist_id: int) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT i.id AS item_id, i.video_id, v.title, v.duration_ms, v.status,
               EXISTS (SELECT 1 FROM movie_management.thumbnails t WHERE t.video_id = v.id) AS has_thumbnail,
               i.sort_order
        FROM movie_management.playlist_items i
        JOIN movie_management.videos v ON v.id = i.video_id
        WHERE i.playlist_id = %s
        ORDER BY i.sort_order ASC
        """,
        (playlist_id,),
    )
    return [dict(row) for row in cur.fetchall()]


_UPDATABLE = ("name", "description")


def update_fields(cur: PgCursor, playlist_id: int, fields: dict[str, Any]) -> None:
    columns = [name for name in _UPDATABLE if name in fields]
    assignments = "".join(f"{name} = %s, " for name in columns)
    cur.execute(
        f"UPDATE movie_management.playlists SET {assignments}updated_at = now() WHERE id = %s",
        (*[fields[name] for name in columns], playlist_id),
    )


def touch(cur: PgCursor, playlist_id: int) -> None:
    cur.execute("UPDATE movie_management.playlists SET updated_at = now() WHERE id = %s", (playlist_id,))


def delete_playlist(cur: PgCursor, playlist_id: int) -> None:
    cur.execute("DELETE FROM movie_management.playlists WHERE id = %s", (playlist_id,))


def count_owned_videos(cur: PgCursor, user_id: int, video_ids: Sequence[int]) -> int:
    if not video_ids:
        return 0
    cur.execute(
        "SELECT count(*) AS n FROM movie_management.videos WHERE user_id = %s AND id = ANY(%s)",
        (user_id, list(video_ids)),
    )
    return int(cur.fetchone()["n"])


def replace_items(cur: PgCursor, playlist_id: int, video_ids: Sequence[int]) -> None:
    """項目をすべて作り直す（並びは 0 始まり）。呼び出し側が 1 つのトランザクションで行う。"""
    cur.execute("DELETE FROM movie_management.playlist_items WHERE playlist_id = %s", (playlist_id,))
    if video_ids:
        execute_values(
            cur,
            "INSERT INTO movie_management.playlist_items (playlist_id, video_id, sort_order) VALUES %s",
            [(playlist_id, video_id, index) for index, video_id in enumerate(video_ids)],
        )


# ---- 再生用 -----------------------------------------------------------

_ITEM_SELECT = """
    SELECT i.id AS item_id, i.playlist_id, i.sort_order, v.id AS video_id, v.title,
           v.duration_ms, v.mime_type, v.status
    FROM movie_management.playlist_items i
    JOIN movie_management.videos v ON v.id = i.video_id
"""


def first_item(cur: PgCursor, playlist_id: int) -> dict[str, Any] | None:
    cur.execute(_ITEM_SELECT + " WHERE i.playlist_id = %s ORDER BY i.sort_order ASC LIMIT 1", (playlist_id,))
    row = cur.fetchone()
    return dict(row) if row is not None else None


def get_item(cur: PgCursor, playlist_id: int, item_id: int) -> dict[str, Any] | None:
    cur.execute(_ITEM_SELECT + " WHERE i.playlist_id = %s AND i.id = %s", (playlist_id, item_id))
    row = cur.fetchone()
    return dict(row) if row is not None else None


def adjacent_item(cur: PgCursor, playlist_id: int, sort_order: int, *, forward: bool) -> dict[str, Any] | None:
    comparison, direction = (">", "ASC") if forward else ("<", "DESC")
    cur.execute(
        _ITEM_SELECT
        + f" WHERE i.playlist_id = %s AND i.sort_order {comparison} %s ORDER BY i.sort_order {direction} LIMIT 1",
        (playlist_id, sort_order),
    )
    row = cur.fetchone()
    return dict(row) if row is not None else None


def has_adjacent(cur: PgCursor, playlist_id: int, sort_order: int, *, forward: bool) -> bool:
    comparison = ">" if forward else "<"
    cur.execute(
        f"""
        SELECT EXISTS (
            SELECT 1 FROM movie_management.playlist_items
            WHERE playlist_id = %s AND sort_order {comparison} %s) AS found
        """,
        (playlist_id, sort_order),
    )
    return bool(cur.fetchone()["found"])
