"""ファイルのデータアクセス。トランザクションは呼び出し側（サービス）が持つ。"""

from __future__ import annotations

from typing import Any

from psycopg2.extensions import cursor as PgCursor

FILE_COLUMNS = "id, folder_id, title, sort_order, is_deleted"


def get_file(cur: PgCursor, user_id: int, file_id: int) -> dict[str, Any] | None:
    """本人のファイル（削除済みを含む）。他ユーザ・存在しないものは None。"""
    cur.execute(
        f"SELECT {FILE_COLUMNS} FROM note_management.files WHERE id = %s AND user_id = %s",
        (file_id, user_id),
    )
    row = cur.fetchone()
    return dict(row) if row is not None else None


def list_files(cur: PgCursor, user_id: int, folder_id: int) -> list[dict[str, Any]]:
    cur.execute(
        f"""
        SELECT {FILE_COLUMNS} FROM note_management.files
        WHERE user_id = %s AND folder_id = %s ORDER BY sort_order ASC, id ASC
        """,
        (user_id, folder_id),
    )
    return [dict(row) for row in cur.fetchall()]


def next_sort_order(cur: PgCursor, user_id: int, folder_id: int) -> int:
    cur.execute(
        "SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM note_management.files "
        "WHERE user_id = %s AND folder_id = %s",
        (user_id, folder_id),
    )
    return int(cur.fetchone()["n"])


def insert_file(cur: PgCursor, user_id: int, folder_id: int, title: str, sort_order: int) -> dict[str, Any]:
    cur.execute(
        f"""
        INSERT INTO note_management.files (user_id, folder_id, title, sort_order)
        VALUES (%s, %s, %s, %s) RETURNING {FILE_COLUMNS}
        """,
        (user_id, folder_id, title, sort_order),
    )
    return dict(cur.fetchone())


def rename_file(cur: PgCursor, file_id: int, title: str) -> dict[str, Any]:
    cur.execute(
        f"UPDATE note_management.files SET title = %s WHERE id = %s RETURNING {FILE_COLUMNS}",
        (title, file_id),
    )
    return dict(cur.fetchone())


def move_file(cur: PgCursor, file_id: int, new_folder_id: int, sort_order: int) -> dict[str, Any]:
    cur.execute(
        f"""
        UPDATE note_management.files SET folder_id = %s, sort_order = %s
        WHERE id = %s RETURNING {FILE_COLUMNS}
        """,
        (new_folder_id, sort_order, file_id),
    )
    return dict(cur.fetchone())


def set_sort_order(cur: PgCursor, file_id: int, sort_order: int) -> None:
    cur.execute("UPDATE note_management.files SET sort_order = %s WHERE id = %s", (sort_order, file_id))


def set_deleted(cur: PgCursor, file_id: int, deleted: bool) -> dict[str, Any]:
    cur.execute(
        f"UPDATE note_management.files SET is_deleted = %s WHERE id = %s RETURNING {FILE_COLUMNS}",
        (deleted, file_id),
    )
    return dict(cur.fetchone())
