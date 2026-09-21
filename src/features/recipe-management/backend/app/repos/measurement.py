from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from psycopg2.extensions import cursor as PgCursor


def list_measurements(cur: PgCursor, user_id: int) -> list[dict[str, Any]]:
    """共通と本人の独自の分量名称を、接頭語・接尾語・識別子の順で返す。"""
    cur.execute(
        """
        SELECT id, name_bef, name_aft, ness_amount, (user_id IS NULL) AS is_system
        FROM recipe_management.measurements
        WHERE user_id IS NULL OR user_id = %s
        ORDER BY name_bef ASC, name_aft ASC, id ASC
        """,
        (user_id,),
    )
    return [dict(row) for row in cur.fetchall()]


def pair_exists(cur: PgCursor, user_id: int, name_bef: str, name_aft: str) -> bool:
    """同じ接頭語と接尾語の組が、共通または本人の独自にあるか。"""
    cur.execute(
        """
        SELECT 1 FROM recipe_management.measurements
        WHERE name_bef = %s AND name_aft = %s AND (user_id IS NULL OR user_id = %s)
        """,
        (name_bef, name_aft, user_id),
    )
    return cur.fetchone() is not None


def insert_measurement(
    cur: PgCursor, user_id: int, name_bef: str, name_aft: str, ness_amount: bool
) -> dict[str, Any]:
    cur.execute(
        """
        INSERT INTO recipe_management.measurements (user_id, name_bef, name_aft, ness_amount)
        VALUES (%s, %s, %s, %s)
        RETURNING id, name_bef, name_aft, ness_amount, false AS is_system
        """,
        (user_id, name_bef, name_aft, ness_amount),
    )
    return dict(cur.fetchone())


def ness_amount_by_id(cur: PgCursor, user_id: int, ids: Sequence[int]) -> dict[int, bool]:
    """指定した分量名称のうち、共通または本人の独自のものの、数量の要否。"""
    if not ids:
        return {}
    cur.execute(
        """
        SELECT id, ness_amount FROM recipe_management.measurements
        WHERE id = ANY(%s) AND (user_id IS NULL OR user_id = %s)
        """,
        (list(ids), user_id),
    )
    return {int(row["id"]): bool(row["ness_amount"]) for row in cur.fetchall()}
