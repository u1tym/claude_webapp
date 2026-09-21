"""DDL の制約（db-design.md）が DB で効いていることを確認する。"""

from __future__ import annotations

from pathlib import Path

import pytest
from psycopg2 import errors

from app.db import get_conn

from conftest import TestUser

SYSTEM_INGREDIENTS = ["砂糖", "塩", "胡椒", "醤油", "みりん", "酒", "味噌", "サラダ油", "卵", "牛乳", "バター", "豆板醤"]


def test_initial_common_data() -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT name FROM recipe_management.ingredients WHERE user_id IS NULL")
        assert sorted(r["name"] for r in cur.fetchall()) == sorted(SYSTEM_INGREDIENTS)
        cur.execute(
            "SELECT name_bef, name_aft, ness_amount FROM recipe_management.measurements WHERE user_id IS NULL"
        )
        assert sorted((r["name_bef"], r["name_aft"], r["ness_amount"]) for r in cur.fetchall()) == sorted(
            [("小さじ", "", True), ("大さじ", "", True), ("", "cc", True), ("ひとつまみ", "", False)]
        )


def test_common_ingredient_name_is_unique() -> None:
    with pytest.raises(errors.UniqueViolation):
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO recipe_management.ingredients (user_id, name, kana) VALUES (NULL, '砂糖', 'x')")


def test_own_ingredient_name_is_unique_per_user(user: TestUser, other_user: TestUser) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        for uid in (user.id, other_user.id):  # 別の利用者なら同じ名前でよい
            cur.execute("INSERT INTO recipe_management.ingredients (user_id, name, kana) VALUES (%s, '独自', 'どくじ')", (uid,))
    with pytest.raises(errors.UniqueViolation):
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO recipe_management.ingredients (user_id, name, kana) VALUES (%s, '独自', 'どくじ')", (user.id,))


def test_blank_names_are_rejected(user: TestUser) -> None:
    for sql in (
        "INSERT INTO recipe_management.ingredients (user_id, name, kana) VALUES (%s, '  ', 'x')",
        "INSERT INTO recipe_management.ingredients (user_id, name, kana) VALUES (%s, 'x', '')",
        "INSERT INTO recipe_management.recipes (user_id, name, kana) VALUES (%s, ' ', 'x')",
        "INSERT INTO recipe_management.recipes (user_id, name, kana) VALUES (%s, 'x', ' ')",
    ):
        with pytest.raises(errors.CheckViolation):
            with get_conn() as conn, conn.cursor() as cur:
                cur.execute(sql, (user.id,))


def test_measurement_needs_prefix_or_suffix(user: TestUser) -> None:
    with pytest.raises(errors.CheckViolation):
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO recipe_management.measurements (user_id, name_bef, name_aft, ness_amount) VALUES (%s, '', '', true)",
                (user.id,),
            )
    with get_conn() as conn, conn.cursor() as cur:  # どちらか一方なら置ける
        cur.execute(
            "INSERT INTO recipe_management.measurements (user_id, name_bef, name_aft, ness_amount) VALUES (%s, '', 'g', true)",
            (user.id,),
        )


def test_common_measurement_pair_is_unique() -> None:
    with pytest.raises(errors.UniqueViolation):
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO recipe_management.measurements (user_id, name_bef, name_aft, ness_amount) VALUES (NULL, '大さじ', '', true)"
            )


def _recipe(cur, user_id: int, name: str, deleted: bool = False) -> int:
    cur.execute(
        "INSERT INTO recipe_management.recipes (user_id, name, kana, is_deleted) VALUES (%s, %s, 'かな', %s) RETURNING id",
        (user_id, name, deleted),
    )
    return int(cur.fetchone()["id"])


def test_recipe_name_is_unique_only_among_active_recipes(user: TestUser) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        _recipe(cur, user.id, "重複", deleted=True)
        _recipe(cur, user.id, "重複", deleted=True)  # 削除済み同士は可
        _recipe(cur, user.id, "重複")  # 削除済みと同名の登録は可
    with pytest.raises(errors.UniqueViolation):
        with get_conn() as conn, conn.cursor() as cur:
            _recipe(cur, user.id, "重複")


def test_step_and_item_numbers_are_unique(user: TestUser) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        recipe_id = _recipe(cur, user.id, "r")
        cur.execute(
            "INSERT INTO recipe_management.recipe_steps (recipe_id, step_no, description) VALUES (%s, 1, 'a') RETURNING id",
            (recipe_id,),
        )
        step_id = int(cur.fetchone()["id"])
    with pytest.raises(errors.UniqueViolation):
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO recipe_management.recipe_steps (recipe_id, step_no, description) VALUES (%s, 1, 'b')", (recipe_id,))
    with pytest.raises(errors.CheckViolation):
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO recipe_management.recipe_steps (recipe_id, step_no, description) VALUES (%s, 0, 'b')", (recipe_id,))
    with pytest.raises(errors.CheckViolation):
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO recipe_management.recipe_steps (recipe_id, step_no, description) VALUES (%s, 2, '  ')", (recipe_id,))
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM recipe_management.ingredients WHERE user_id IS NULL LIMIT 1")
        ing = int(cur.fetchone()["id"])
        cur.execute("SELECT id FROM recipe_management.measurements WHERE user_id IS NULL LIMIT 1")
        meas = int(cur.fetchone()["id"])
        cur.execute(
            "INSERT INTO recipe_management.recipe_step_items (step_id, item_no, ingredient_id, measurement_id) VALUES (%s, 1, %s, %s)",
            (step_id, ing, meas),
        )
    with pytest.raises(errors.UniqueViolation):
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO recipe_management.recipe_step_items (step_id, item_no, ingredient_id, measurement_id) VALUES (%s, 1, %s, %s)",
                (step_id, ing, meas),
            )


def test_master_rows_in_use_cannot_be_deleted(user: TestUser) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        recipe_id = _recipe(cur, user.id, "r")
        cur.execute(
            "INSERT INTO recipe_management.recipe_steps (recipe_id, step_no, description) VALUES (%s, 1, 'a') RETURNING id",
            (recipe_id,),
        )
        step_id = int(cur.fetchone()["id"])
        cur.execute("INSERT INTO recipe_management.ingredients (user_id, name, kana) VALUES (%s, '使用中', 'しようちゅう') RETURNING id", (user.id,))
        ing = int(cur.fetchone()["id"])
        cur.execute("SELECT id FROM recipe_management.measurements WHERE user_id IS NULL LIMIT 1")
        meas = int(cur.fetchone()["id"])
        cur.execute(
            "INSERT INTO recipe_management.recipe_step_items (step_id, item_no, ingredient_id, measurement_id) VALUES (%s, 1, %s, %s)",
            (step_id, ing, meas),
        )
    with pytest.raises(errors.ForeignKeyViolation):
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM recipe_management.ingredients WHERE id = %s", (ing,))


def test_deleting_recipe_cascades_to_steps_and_items(user: TestUser) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        recipe_id = _recipe(cur, user.id, "r")
        cur.execute(
            "INSERT INTO recipe_management.recipe_steps (recipe_id, step_no, description) VALUES (%s, 1, 'a') RETURNING id",
            (recipe_id,),
        )
        step_id = int(cur.fetchone()["id"])
        cur.execute("SELECT id FROM recipe_management.ingredients WHERE user_id IS NULL LIMIT 1")
        ing = int(cur.fetchone()["id"])
        cur.execute("SELECT id FROM recipe_management.measurements WHERE user_id IS NULL LIMIT 1")
        meas = int(cur.fetchone()["id"])
        cur.execute(
            "INSERT INTO recipe_management.recipe_step_items (step_id, item_no, ingredient_id, measurement_id) VALUES (%s, 1, %s, %s)",
            (step_id, ing, meas),
        )
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM recipe_management.recipes WHERE id = %s", (recipe_id,))
        cur.execute("SELECT count(*) AS n FROM recipe_management.recipe_steps WHERE recipe_id = %s", (recipe_id,))
        assert cur.fetchone()["n"] == 0
        cur.execute("SELECT count(*) AS n FROM recipe_management.recipe_step_items WHERE step_id = %s", (step_id,))
        assert cur.fetchone()["n"] == 0


def test_ddl_is_reapplicable() -> None:
    sql = (Path(__file__).resolve().parent.parent / "backend" / "sql" / "01_recipe_management.sql").read_text(encoding="utf-8")
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql)
        cur.execute("SELECT count(*) AS n FROM recipe_management.ingredients WHERE user_id IS NULL")
        assert cur.fetchone()["n"] == 12
        cur.execute("SELECT count(*) AS n FROM recipe_management.measurements WHERE user_id IS NULL")
        assert cur.fetchone()["n"] == 4
