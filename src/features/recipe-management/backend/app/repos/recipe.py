from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from psycopg2.extensions import cursor as PgCursor
from psycopg2.extras import execute_values


def list_recipes(cur: PgCursor, user_id: int) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT id, name, kana FROM recipe_management.recipes
        WHERE user_id = %s AND is_deleted = false
        ORDER BY kana ASC, id ASC
        """,
        (user_id,),
    )
    return [dict(row) for row in cur.fetchall()]


def get_recipe(cur: PgCursor, user_id: int, recipe_id: int, *, lock: bool = False) -> dict[str, Any] | None:
    """本人の、削除されていないレシピ。他ユーザ・削除済み・存在しないものは None。"""
    cur.execute(
        f"""
        SELECT id, name, kana, created_at, updated_at FROM recipe_management.recipes
        WHERE id = %s AND user_id = %s AND is_deleted = false
        {"FOR UPDATE" if lock else ""}
        """,
        (recipe_id, user_id),
    )
    row = cur.fetchone()
    return dict(row) if row is not None else None


def insert_recipe(cur: PgCursor, user_id: int, name: str, kana: str) -> int:
    cur.execute(
        "INSERT INTO recipe_management.recipes (user_id, name, kana) VALUES (%s, %s, %s) RETURNING id",
        (user_id, name, kana),
    )
    return int(cur.fetchone()["id"])


def update_recipe(cur: PgCursor, recipe_id: int, name: str, kana: str) -> None:
    cur.execute(
        "UPDATE recipe_management.recipes SET name = %s, kana = %s, updated_at = now() WHERE id = %s",
        (name, kana, recipe_id),
    )


def soft_delete(cur: PgCursor, user_id: int, recipe_id: int) -> bool:
    cur.execute(
        """
        UPDATE recipe_management.recipes SET is_deleted = true, updated_at = now()
        WHERE id = %s AND user_id = %s AND is_deleted = false
        RETURNING id
        """,
        (recipe_id, user_id),
    )
    return cur.fetchone() is not None


def delete_steps(cur: PgCursor, recipe_id: int) -> None:
    """工程を物理削除する（工程の材料の行は連鎖して消える）。"""
    cur.execute("DELETE FROM recipe_management.recipe_steps WHERE recipe_id = %s", (recipe_id,))


def insert_step(cur: PgCursor, recipe_id: int, step_no: int, description: str) -> int:
    cur.execute(
        """
        INSERT INTO recipe_management.recipe_steps (recipe_id, step_no, description)
        VALUES (%s, %s, %s) RETURNING id
        """,
        (recipe_id, step_no, description),
    )
    return int(cur.fetchone()["id"])


def insert_items(cur: PgCursor, step_id: int, items: Sequence[tuple[int, int, str]]) -> None:
    """items = [(材料の識別子, 分量名称の識別子, 数量)]。並びは 1 から、入力の順。"""
    if not items:
        return
    execute_values(
        cur,
        """
        INSERT INTO recipe_management.recipe_step_items
            (step_id, item_no, ingredient_id, measurement_id, amount) VALUES %s
        """,
        [(step_id, no, ing, meas, amount) for no, (ing, meas, amount) in enumerate(items, start=1)],
    )


def fetch_steps(cur: PgCursor, recipe_id: int) -> list[dict[str, Any]]:
    """工程と材料の行を、工程番号・並びの順に、工程ごとにまとめて返す。"""
    cur.execute(
        """
        SELECT s.step_no, s.description,
               i.item_no, i.amount,
               ing.id AS ing_id, ing.name AS ing_name, ing.kana AS ing_kana, (ing.user_id IS NULL) AS ing_system,
               m.id AS m_id, m.name_bef, m.name_aft, m.ness_amount, (m.user_id IS NULL) AS m_system
        FROM recipe_management.recipe_steps s
        LEFT JOIN recipe_management.recipe_step_items i ON i.step_id = s.id
        LEFT JOIN recipe_management.ingredients ing ON ing.id = i.ingredient_id
        LEFT JOIN recipe_management.measurements m ON m.id = i.measurement_id
        WHERE s.recipe_id = %s
        ORDER BY s.step_no ASC, i.item_no ASC
        """,
        (recipe_id,),
    )
    steps: list[dict[str, Any]] = []
    for row in cur.fetchall():
        if not steps or steps[-1]["step_no"] != row["step_no"]:
            steps.append({"step_no": row["step_no"], "description": row["description"], "items": []})
        if row["item_no"] is not None:
            steps[-1]["items"].append(
                {
                    "item_no": row["item_no"],
                    "ingredient": {
                        "id": row["ing_id"],
                        "name": row["ing_name"],
                        "kana": row["ing_kana"],
                        "is_system": row["ing_system"],
                    },
                    "measurement": {
                        "id": row["m_id"],
                        "name_bef": row["name_bef"],
                        "name_aft": row["name_aft"],
                        "ness_amount": row["ness_amount"],
                        "is_system": row["m_system"],
                    },
                    "amount": row["amount"],
                }
            )
    return steps
