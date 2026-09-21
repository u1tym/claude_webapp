"""DDL の制約・インデックスが、DB で効いていることを直接確認する（db-design.md）。"""

from __future__ import annotations

from pathlib import Path

import psycopg2.errors
import pytest

from app.db import get_conn

from conftest import TestUser

SQL_FILE = Path(__file__).resolve().parent.parent / "backend" / "sql" / "01_note_management.sql"

FOLDER = "INSERT INTO note_management.folders (user_id, parent_id, name, sort_order, is_deleted) VALUES (%s, %s, %s, %s, %s) RETURNING id"
FILE = "INSERT INTO note_management.files (user_id, folder_id, title, sort_order, is_deleted) VALUES (%s, %s, %s, %s, %s) RETURNING id"


def _one(cur, sql: str, params: tuple) -> int:
    cur.execute(sql, params)
    return int(cur.fetchone()["id"])


def _part(cur, user_id: int, file_id: int, order: int, ptype: str = "text", **extra) -> int:
    cols = {"user_id": user_id, "file_id": file_id, "sort_order": order, "ptype": ptype, **extra}
    names = ", ".join(cols)
    marks = ", ".join(["%s"] * len(cols))
    return _one(cur, f"INSERT INTO note_management.parts ({names}) VALUES ({marks}) RETURNING id", tuple(cols.values()))


def test_ddl_can_be_applied_again() -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(SQL_FILE.read_text(encoding="utf-8"))


def test_tables_exist() -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'note_management'")
        names = {r["table_name"] for r in cur.fetchall()}
    assert names == {
        "folders", "files", "parts", "part_revisions", "checklists", "checklist_categories", "checklist_items",
    }


def test_folder_name_is_unique_only_among_live_rows(user: TestUser) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        root = _one(cur, FOLDER, (user.id, None, "A", 1, False))
        # ルートの同名（削除されていない）は不可、削除済み同士・削除済みとの同名は可
        _one(cur, FOLDER, (user.id, None, "A", 2, True))
        _one(cur, FOLDER, (user.id, None, "A", 3, True))
        # 子も同様
        _one(cur, FOLDER, (user.id, root, "c", 1, False))
        _one(cur, FOLDER, (user.id, root, "c", 2, True))
    with pytest.raises(psycopg2.errors.UniqueViolation) as err:
        with get_conn() as conn, conn.cursor() as cur:
            _one(cur, FOLDER, (user.id, None, "A", 9, False))
    assert err.value.diag.constraint_name == "folders_root_name_uidx"
    with pytest.raises(psycopg2.errors.UniqueViolation) as err:
        with get_conn() as conn, conn.cursor() as cur:
            _one(cur, FOLDER, (user.id, root, "c", 9, False))
    assert err.value.diag.constraint_name == "folders_child_name_uidx"


def test_folder_same_name_under_different_parents_is_allowed(user: TestUser) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        a = _one(cur, FOLDER, (user.id, None, "A", 1, False))
        b = _one(cur, FOLDER, (user.id, None, "B", 2, False))
        _one(cur, FOLDER, (user.id, a, "x", 1, False))
        _one(cur, FOLDER, (user.id, b, "x", 1, False))


def test_folder_sort_order_is_unique_per_parent_including_deleted(user: TestUser) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        root = _one(cur, FOLDER, (user.id, None, "A", 1, False))
        _one(cur, FOLDER, (user.id, root, "c1", 1, True))
    with pytest.raises(psycopg2.errors.UniqueViolation) as err:
        with get_conn() as conn, conn.cursor() as cur:
            _one(cur, FOLDER, (user.id, None, "B", 1, False))  # ルートの並び順 1 は使用済み
    assert err.value.diag.constraint_name == "folders_root_order_uidx"
    with pytest.raises(psycopg2.errors.UniqueViolation) as err:
        with get_conn() as conn, conn.cursor() as cur:
            _one(cur, FOLDER, (user.id, root, "c2", 1, False))  # 削除済みも並び順を占める
    assert err.value.diag.constraint_name == "folders_child_order_uidx"


def test_folder_name_must_not_be_blank(user: TestUser) -> None:
    with pytest.raises(psycopg2.errors.CheckViolation):
        with get_conn() as conn, conn.cursor() as cur:
            _one(cur, FOLDER, (user.id, None, "   ", 1, False))


def test_file_title_and_order(user: TestUser) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        folder = _one(cur, FOLDER, (user.id, None, "A", 1, False))
        _one(cur, FILE, (user.id, folder, "t", 1, False))
        _one(cur, FILE, (user.id, folder, "t", 2, True))
    with pytest.raises(psycopg2.errors.UniqueViolation) as err:
        with get_conn() as conn, conn.cursor() as cur:
            _one(cur, FILE, (user.id, folder, "t", 3, False))
    assert err.value.diag.constraint_name == "files_title_uidx"
    with pytest.raises(psycopg2.errors.UniqueViolation) as err:
        with get_conn() as conn, conn.cursor() as cur:
            _one(cur, FILE, (user.id, folder, "u", 2, False))
    assert err.value.diag.constraint_name == "files_order_uidx"
    with pytest.raises(psycopg2.errors.CheckViolation):
        with get_conn() as conn, conn.cursor() as cur:
            _one(cur, FILE, (user.id, folder, " ", 9, False))


def _folder_and_file(user_id: int) -> int:
    with get_conn() as conn, conn.cursor() as cur:
        folder = _one(cur, FOLDER, (user_id, None, "F", 1, False))
        return _one(cur, FILE, (user_id, folder, "f", 1, False))


def test_part_constraints(user: TestUser) -> None:
    file_id = _folder_and_file(user.id)
    with get_conn() as conn, conn.cursor() as cur:
        _part(cur, user.id, file_id, 1)
        _part(cur, user.id, file_id, 2, "png", filename="a.png", data="AAAA", byte_size=3)

    def fails(exc: type[Exception], order: int, ptype: str = "text", **extra) -> None:
        with pytest.raises(exc):
            with get_conn() as conn, conn.cursor() as cur:
                _part(cur, user.id, file_id, order, ptype, **extra)

    fails(psycopg2.errors.UniqueViolation, 1)  # 並び順の重複
    fails(psycopg2.errors.CheckViolation, 10, "table")  # 種別の値
    fails(psycopg2.errors.CheckViolation, 11, "jpeg", filename="  ")  # 画像はファイル名が必須
    fails(psycopg2.errors.CheckViolation, 12, "binary")  # バイナリもファイル名が必須
    fails(psycopg2.errors.CheckViolation, 13, "png", filename="a.png", image_scale=0.2)
    fails(psycopg2.errors.CheckViolation, 14, "png", filename="a.png", image_scale=4.5)
    fails(psycopg2.errors.CheckViolation, 15, byte_size=-1)
    fails(psycopg2.errors.CheckViolation, 16, markers='{"a": 1}')  # 配列でない
    with get_conn() as conn, conn.cursor() as cur:
        _part(cur, user.id, file_id, 17, "png", filename="a.png", image_scale=0.25)
        _part(cur, user.id, file_id, 18, "png", filename="a.png", image_scale=4.0)


def test_revisions_cascade_and_unique(user: TestUser) -> None:
    file_id = _folder_and_file(user.id)
    with get_conn() as conn, conn.cursor() as cur:
        part = _part(cur, user.id, file_id, 1, "binary", filename="a.bin", data="AAAA", byte_size=3)
        cur.execute(
            "INSERT INTO note_management.part_revisions (user_id, part_id, revision_number, ptype, filename, data) "
            "VALUES (%s, %s, 1, 'binary', 'a.bin', 'AAAA')",
            (user.id, part),
        )
    with pytest.raises(psycopg2.errors.UniqueViolation):
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO note_management.part_revisions (user_id, part_id, revision_number, ptype, filename, data) "
                "VALUES (%s, %s, 1, 'binary', 'b.bin', 'AAAA')",
                (user.id, part),
            )
    with pytest.raises(psycopg2.errors.CheckViolation):
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO note_management.part_revisions (user_id, part_id, revision_number, ptype, filename, data) "
                "VALUES (%s, %s, 2, 'text', 'b.bin', 'AAAA')",
                (user.id, part),
            )
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM note_management.parts WHERE id = %s", (part,))
        cur.execute("SELECT count(*) AS n FROM note_management.part_revisions WHERE part_id = %s", (part,))
        assert cur.fetchone()["n"] == 0


def test_checklist_constraints_and_cascade(user: TestUser) -> None:
    file_id = _folder_and_file(user.id)
    with get_conn() as conn, conn.cursor() as cur:
        part = _part(cur, user.id, file_id, 1, "checklist")
        cl = _one(cur, "INSERT INTO note_management.checklists (user_id, part_id) VALUES (%s, %s) RETURNING id", (user.id, part))
        cat = _one(
            cur,
            "INSERT INTO note_management.checklist_categories (checklist_id, name, sort_order) VALUES (%s, 'a', 1) RETURNING id",
            (cl,),
        )
        cur.execute("INSERT INTO note_management.checklist_categories (checklist_id, name, is_deleted) VALUES (%s, 'a', true)", (cl,))
        cur.execute("INSERT INTO note_management.checklist_items (checklist_id, category_id, title) VALUES (%s, %s, 'x')", (cl, cat))
    with pytest.raises(psycopg2.errors.UniqueViolation):  # 1 パーツに 1 チェックリスト
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO note_management.checklists (user_id, part_id) VALUES (%s, %s)", (user.id, part))
    with pytest.raises(psycopg2.errors.UniqueViolation):  # 削除されていないカテゴリの同名は不可（無名も 1 つ）
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO note_management.checklist_categories (checklist_id, name) VALUES (%s, 'a')", (cl,))
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO note_management.checklist_categories (checklist_id, name) VALUES (%s, '')", (cl,))
    with pytest.raises(psycopg2.errors.UniqueViolation):
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO note_management.checklist_categories (checklist_id, name) VALUES (%s, '')", (cl,))
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM note_management.parts WHERE id = %s", (part,))
        for table in ("checklists", "checklist_categories", "checklist_items"):
            cur.execute(f"SELECT count(*) AS n FROM note_management.{table} WHERE " + ("part_id = %s" if table == "checklists" else "checklist_id = %s"), (part if table == "checklists" else cl,))
            assert cur.fetchone()["n"] == 0, table
