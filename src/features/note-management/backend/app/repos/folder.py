"""フォルダのデータアクセス。トランザクションは呼び出し側（サービス）が持つ。"""

from __future__ import annotations

from typing import Any

from psycopg2.extensions import cursor as PgCursor

FOLDER_COLUMNS = "id, parent_id, name, sort_order, is_deleted"

# 並び順の採番・入れ替えを、同じ親の中で直列にするための、アドバイザリロックの名前空間
_LOCK_NS_SIBLINGS = 10


def lock_siblings(cur: PgCursor, user_id: int, parent_id: int | None) -> None:
    """同じ親（フォルダの中のフォルダ・ファイル。ルートは利用者ごと）の中の並び順の操作を、直列にする。"""
    key = parent_id if parent_id is not None else -user_id
    cur.execute("SELECT pg_advisory_xact_lock(%s, %s)", (_LOCK_NS_SIBLINGS, key))


def get_folder(cur: PgCursor, user_id: int, folder_id: int) -> dict[str, Any] | None:
    """本人のフォルダ（削除済みを含む）。他ユーザ・存在しないものは None。"""
    cur.execute(
        f"SELECT {FOLDER_COLUMNS} FROM note_management.folders WHERE id = %s AND user_id = %s",
        (folder_id, user_id),
    )
    row = cur.fetchone()
    return dict(row) if row is not None else None


def chain_deleted(cur: PgCursor, folder_id: int) -> bool:
    """そのフォルダ自身、または上位のいずれかが削除済みか。"""
    cur.execute(
        """
        WITH RECURSIVE chain AS (
            SELECT id, parent_id, is_deleted FROM note_management.folders WHERE id = %s
            UNION ALL
            SELECT p.id, p.parent_id, p.is_deleted
            FROM note_management.folders p JOIN chain c ON p.id = c.parent_id
        )
        SELECT COALESCE(bool_or(is_deleted), false) AS deleted FROM chain
        """,
        (folder_id,),
    )
    return bool(cur.fetchone()["deleted"])


def ancestors_deleted(cur: PgCursor, parent_id: int | None) -> bool:
    """親（None はルート）から上のいずれかが削除済みか。子の「上位が削除済み」の判定に使う。"""
    if parent_id is None:
        return False
    return chain_deleted(cur, parent_id)


def is_self_or_descendant(cur: PgCursor, folder_id: int, target_id: int) -> bool:
    """target_id が、folder_id 自身、またはその子孫か（target から上へたどって folder_id に着くか）。"""
    cur.execute(
        """
        WITH RECURSIVE chain AS (
            SELECT id, parent_id FROM note_management.folders WHERE id = %s
            UNION ALL
            SELECT p.id, p.parent_id
            FROM note_management.folders p JOIN chain c ON p.id = c.parent_id
        )
        SELECT EXISTS (SELECT 1 FROM chain WHERE id = %s) AS found
        """,
        (target_id, folder_id),
    )
    return bool(cur.fetchone()["found"])


def list_children(cur: PgCursor, user_id: int, parent_id: int | None) -> list[dict[str, Any]]:
    if parent_id is None:
        cur.execute(
            f"""
            SELECT {FOLDER_COLUMNS} FROM note_management.folders
            WHERE user_id = %s AND parent_id IS NULL ORDER BY sort_order ASC, id ASC
            """,
            (user_id,),
        )
    else:
        cur.execute(
            f"""
            SELECT {FOLDER_COLUMNS} FROM note_management.folders
            WHERE user_id = %s AND parent_id = %s ORDER BY sort_order ASC, id ASC
            """,
            (user_id, parent_id),
        )
    return [dict(row) for row in cur.fetchall()]


def next_sort_order(cur: PgCursor, user_id: int, parent_id: int | None) -> int:
    """同じ親の中の、削除済みを含む最大の並び順 + 1（なければ 1）。"""
    if parent_id is None:
        cur.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM note_management.folders "
            "WHERE user_id = %s AND parent_id IS NULL",
            (user_id,),
        )
    else:
        cur.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM note_management.folders "
            "WHERE user_id = %s AND parent_id = %s",
            (user_id, parent_id),
        )
    return int(cur.fetchone()["n"])


def insert_folder(cur: PgCursor, user_id: int, parent_id: int | None, name: str, sort_order: int) -> dict[str, Any]:
    cur.execute(
        f"""
        INSERT INTO note_management.folders (user_id, parent_id, name, sort_order)
        VALUES (%s, %s, %s, %s) RETURNING {FOLDER_COLUMNS}
        """,
        (user_id, parent_id, name, sort_order),
    )
    return dict(cur.fetchone())


def rename_folder(cur: PgCursor, folder_id: int, name: str) -> dict[str, Any]:
    cur.execute(
        f"UPDATE note_management.folders SET name = %s WHERE id = %s RETURNING {FOLDER_COLUMNS}",
        (name, folder_id),
    )
    return dict(cur.fetchone())


def move_folder(cur: PgCursor, folder_id: int, new_parent_id: int | None, sort_order: int) -> dict[str, Any]:
    cur.execute(
        f"""
        UPDATE note_management.folders SET parent_id = %s, sort_order = %s
        WHERE id = %s RETURNING {FOLDER_COLUMNS}
        """,
        (new_parent_id, sort_order, folder_id),
    )
    return dict(cur.fetchone())


def set_sort_order(cur: PgCursor, folder_id: int, sort_order: int) -> None:
    cur.execute("UPDATE note_management.folders SET sort_order = %s WHERE id = %s", (sort_order, folder_id))


def set_deleted(cur: PgCursor, folder_id: int, deleted: bool) -> dict[str, Any]:
    cur.execute(
        f"UPDATE note_management.folders SET is_deleted = %s WHERE id = %s RETURNING {FOLDER_COLUMNS}",
        (deleted, folder_id),
    )
    return dict(cur.fetchone())
