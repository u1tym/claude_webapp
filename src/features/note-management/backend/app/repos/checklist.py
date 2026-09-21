"""チェックリスト・カテゴリ・項目のデータアクセス。トランザクションは呼び出し側が持つ。"""

from __future__ import annotations

from typing import Any

from psycopg2.extensions import cursor as PgCursor


def get_checklist(cur: PgCursor, user_id: int, checklist_id: int, *, lock: bool = False) -> dict[str, Any] | None:
    """本人のチェックリスト。他ユーザ・存在しないものは None。lock で行ロック（変更の直列化）。"""
    cur.execute(
        f"""
        SELECT c.id, c.part_id, c.title, p.is_deleted AS part_deleted, p.file_id
        FROM note_management.checklists c JOIN note_management.parts p ON p.id = c.part_id
        WHERE c.id = %s AND c.user_id = %s
        {"FOR UPDATE OF c" if lock else ""}
        """,
        (checklist_id, user_id),
    )
    row = cur.fetchone()
    return dict(row) if row is not None else None


def set_title(cur: PgCursor, checklist_id: int, title: str) -> None:
    cur.execute("UPDATE note_management.checklists SET title = %s WHERE id = %s", (title, checklist_id))


def live_categories(cur: PgCursor, checklist_id: int) -> list[dict[str, Any]]:
    """削除されていないカテゴリ。無名（名前が空）が先頭、続いて名前のあるカテゴリが表示順。"""
    cur.execute(
        """
        SELECT id, name, sort_order FROM note_management.checklist_categories
        WHERE checklist_id = %s AND NOT is_deleted
        ORDER BY (name <> ''), sort_order ASC, id ASC
        """,
        (checklist_id,),
    )
    return [dict(r) for r in cur.fetchall()]


def get_live_category(cur: PgCursor, checklist_id: int, category_id: int) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT id, name, sort_order FROM note_management.checklist_categories
        WHERE id = %s AND checklist_id = %s AND NOT is_deleted
        """,
        (category_id, checklist_id),
    )
    row = cur.fetchone()
    return dict(row) if row is not None else None


def get_unnamed_category(cur: PgCursor, checklist_id: int) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT id, name, sort_order FROM note_management.checklist_categories
        WHERE checklist_id = %s AND name = '' AND NOT is_deleted
        """,
        (checklist_id,),
    )
    row = cur.fetchone()
    return dict(row) if row is not None else None


def insert_category(cur: PgCursor, checklist_id: int, name: str, sort_order: int | None = None) -> int:
    if sort_order is None:
        cur.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM note_management.checklist_categories WHERE checklist_id = %s",
            (checklist_id,),
        )
        sort_order = int(cur.fetchone()["n"])
    cur.execute(
        """
        INSERT INTO note_management.checklist_categories (checklist_id, name, sort_order)
        VALUES (%s, %s, %s) RETURNING id
        """,
        (checklist_id, name, sort_order),
    )
    return int(cur.fetchone()["id"])


def rename_category(cur: PgCursor, category_id: int, name: str) -> None:
    cur.execute("UPDATE note_management.checklist_categories SET name = %s WHERE id = %s", (name, category_id))


def delete_category(cur: PgCursor, category_id: int) -> None:
    """カテゴリと、その中の項目を、論理削除する。"""
    cur.execute("UPDATE note_management.checklist_categories SET is_deleted = true WHERE id = %s", (category_id,))
    cur.execute("UPDATE note_management.checklist_items SET is_deleted = true WHERE category_id = %s", (category_id,))


def set_category_order(cur: PgCursor, category_id: int, sort_order: int) -> None:
    cur.execute("UPDATE note_management.checklist_categories SET sort_order = %s WHERE id = %s", (sort_order, category_id))


def live_items(cur: PgCursor, checklist_id: int) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT id, category_id, title, is_checked, sort_order FROM note_management.checklist_items
        WHERE checklist_id = %s AND NOT is_deleted ORDER BY category_id, sort_order ASC, id ASC
        """,
        (checklist_id,),
    )
    return [dict(r) for r in cur.fetchall()]


def category_items(cur: PgCursor, category_id: int) -> list[int]:
    """カテゴリの、削除されていない項目の識別子（表示順）。"""
    cur.execute(
        """
        SELECT id FROM note_management.checklist_items
        WHERE category_id = %s AND NOT is_deleted ORDER BY sort_order ASC, id ASC
        """,
        (category_id,),
    )
    return [int(r["id"]) for r in cur.fetchall()]


def get_live_item(cur: PgCursor, checklist_id: int, item_id: int) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT id, category_id, title, is_checked FROM note_management.checklist_items
        WHERE id = %s AND checklist_id = %s AND NOT is_deleted
        """,
        (item_id, checklist_id),
    )
    row = cur.fetchone()
    return dict(row) if row is not None else None


def insert_item(cur: PgCursor, checklist_id: int, category_id: int, title: str) -> int:
    cur.execute(
        "SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM note_management.checklist_items WHERE category_id = %s",
        (category_id,),
    )
    order = int(cur.fetchone()["n"])
    cur.execute(
        """
        INSERT INTO note_management.checklist_items (checklist_id, category_id, title, sort_order)
        VALUES (%s, %s, %s, %s) RETURNING id
        """,
        (checklist_id, category_id, title, order),
    )
    return int(cur.fetchone()["id"])


def update_item(cur: PgCursor, item_id: int, title: str | None, is_checked: bool | None) -> None:
    cur.execute(
        """
        UPDATE note_management.checklist_items
        SET title = COALESCE(%s, title), is_checked = COALESCE(%s, is_checked) WHERE id = %s
        """,
        (title, is_checked, item_id),
    )


def delete_item(cur: PgCursor, item_id: int) -> None:
    cur.execute("UPDATE note_management.checklist_items SET is_deleted = true WHERE id = %s", (item_id,))


def place_items(cur: PgCursor, category_id: int, ordered_ids: list[int]) -> None:
    """指定した項目を、そのカテゴリの、指定した順（1 から）に付け直す。"""
    for index, item_id in enumerate(ordered_ids, start=1):
        cur.execute(
            "UPDATE note_management.checklist_items SET category_id = %s, sort_order = %s WHERE id = %s",
            (category_id, index, item_id),
        )
