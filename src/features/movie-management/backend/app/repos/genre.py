from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from psycopg2.extensions import cursor as PgCursor


def list_genres(cur: PgCursor, user_id: int) -> list[dict[str, Any]]:
    """共通ジャンル（user_id が NULL）と本人の独自ジャンルを表示順で返す。"""
    cur.execute(
        """
        SELECT id, name, sort_order, (user_id IS NULL) AS is_system
        FROM movie_management.genres
        WHERE user_id IS NULL OR user_id = %s
        ORDER BY sort_order ASC, id ASC
        """,
        (user_id,),
    )
    return [dict(row) for row in cur.fetchall()]


def insert_genre(cur: PgCursor, user_id: int, name: str, sort_order: int) -> dict[str, Any]:
    cur.execute(
        """
        INSERT INTO movie_management.genres (user_id, name, sort_order)
        VALUES (%s, %s, %s)
        RETURNING id, name, sort_order, false AS is_system
        """,
        (user_id, name, sort_order),
    )
    return dict(cur.fetchone())


def count_accessible(cur: PgCursor, user_id: int, genre_ids: Sequence[int]) -> int:
    """指定したジャンルのうち、共通または本人の独自ジャンルである件数。"""
    if not genre_ids:
        return 0
    cur.execute(
        """
        SELECT count(*) AS n
        FROM movie_management.genres
        WHERE id = ANY(%s) AND (user_id IS NULL OR user_id = %s)
        """,
        (list(genre_ids), user_id),
    )
    return int(cur.fetchone()["n"])
