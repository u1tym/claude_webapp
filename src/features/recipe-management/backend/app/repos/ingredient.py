from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from psycopg2.extensions import cursor as PgCursor


def list_ingredients(cur: PgCursor, user_id: int) -> list[dict[str, Any]]:
    """共通（user_id が NULL）と本人の独自の材料を、かな・識別子の順で返す。"""
    cur.execute(
        """
        SELECT id, name, kana, (user_id IS NULL) AS is_system
        FROM recipe_management.ingredients
        WHERE user_id IS NULL OR user_id = %s
        ORDER BY kana ASC, id ASC
        """,
        (user_id,),
    )
    return [dict(row) for row in cur.fetchall()]


def name_exists(cur: PgCursor, user_id: int, name: str) -> bool:
    """同じ名前の材料が、共通または本人の独自にあるか。"""
    cur.execute(
        """
        SELECT 1 FROM recipe_management.ingredients
        WHERE name = %s AND (user_id IS NULL OR user_id = %s)
        """,
        (name, user_id),
    )
    return cur.fetchone() is not None


def insert_ingredient(cur: PgCursor, user_id: int, name: str, kana: str) -> dict[str, Any]:
    cur.execute(
        """
        INSERT INTO recipe_management.ingredients (user_id, name, kana)
        VALUES (%s, %s, %s)
        RETURNING id, name, kana, false AS is_system
        """,
        (user_id, name, kana),
    )
    return dict(cur.fetchone())


def count_accessible(cur: PgCursor, user_id: int, ids: Sequence[int]) -> int:
    """指定した材料のうち、共通または本人の独自である件数。"""
    if not ids:
        return 0
    cur.execute(
        """
        SELECT count(*) AS n FROM recipe_management.ingredients
        WHERE id = ANY(%s) AND (user_id IS NULL OR user_id = %s)
        """,
        (list(ids), user_id),
    )
    return int(cur.fetchone()["n"])
