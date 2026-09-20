from __future__ import annotations

from typing import Any

from psycopg2.extensions import cursor as PgCursor

_COLUMNS = "id, title, description, created_at, updated_at"


def count_series(cur: PgCursor, user_id: int, pattern: str | None) -> int:
    cur.execute(
        """
        SELECT count(*) AS n FROM movie_management.series
        WHERE user_id = %s AND (%s::text IS NULL OR title ILIKE %s)
        """,
        (user_id, pattern, pattern),
    )
    return int(cur.fetchone()["n"])


def list_series(
    cur: PgCursor, user_id: int, pattern: str | None, limit: int, offset: int
) -> list[dict[str, Any]]:
    cur.execute(
        f"""
        SELECT {_COLUMNS} FROM movie_management.series
        WHERE user_id = %s AND (%s::text IS NULL OR title ILIKE %s)
        ORDER BY created_at DESC, id DESC
        LIMIT %s OFFSET %s
        """,
        (user_id, pattern, pattern, limit, offset),
    )
    return [dict(row) for row in cur.fetchall()]


def insert_series(cur: PgCursor, user_id: int, title: str, description: str | None) -> dict[str, Any]:
    cur.execute(
        f"""
        INSERT INTO movie_management.series (user_id, title, description)
        VALUES (%s, %s, %s)
        RETURNING {_COLUMNS}
        """,
        (user_id, title, description),
    )
    return dict(cur.fetchone())


def get_series(cur: PgCursor, user_id: int, series_id: int) -> dict[str, Any] | None:
    cur.execute(
        f"SELECT {_COLUMNS} FROM movie_management.series WHERE id = %s AND user_id = %s",
        (series_id, user_id),
    )
    row = cur.fetchone()
    return dict(row) if row is not None else None


def list_series_videos(cur: PgCursor, user_id: int, series_id: int) -> list[dict[str, Any]]:
    """作品に属する本人の動画（全状態）を、作品内順序・話数の順で返す。"""
    cur.execute(
        """
        SELECT id, title, episode_number, episode_title, sort_order, duration_ms, status
        FROM movie_management.videos
        WHERE series_id = %s AND user_id = %s
        ORDER BY sort_order ASC, episode_number ASC NULLS LAST, id ASC
        """,
        (series_id, user_id),
    )
    return [dict(row) for row in cur.fetchall()]
