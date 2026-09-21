"""パーツ・過去世代・チェックリストの紐づけのデータアクセス。トランザクションは呼び出し側が持つ。"""

from __future__ import annotations

import json
from typing import Any

from psycopg2.extensions import cursor as PgCursor

BINARY_TYPES = ("jpeg", "png", "binary")

# 画像・バイナリの中身（Base64）は、一覧・取得では読まない
_LIGHT_COLUMNS = """
    id, file_id, sort_order, is_deleted, ptype,
    CASE WHEN ptype IN ('jpeg', 'png', 'binary') THEN '' ELSE data END AS data,
    byte_size, filename, title, markers, image_scale
"""

_LOCK_NS_PARTS = 11


def lock_parts(cur: PgCursor, file_id: int) -> None:
    """同じファイルの中の、パーツの並び順の操作を直列にする。"""
    cur.execute("SELECT pg_advisory_xact_lock(%s, %s)", (_LOCK_NS_PARTS, file_id))


def get_part(cur: PgCursor, user_id: int, part_id: int) -> dict[str, Any] | None:
    """本人のパーツ（削除済みを含む。画像・バイナリの中身は含まない）。"""
    cur.execute(
        f"SELECT {_LIGHT_COLUMNS} FROM note_management.parts WHERE id = %s AND user_id = %s",
        (part_id, user_id),
    )
    row = cur.fetchone()
    return dict(row) if row is not None else None


def list_parts(cur: PgCursor, user_id: int, file_id: int, include_deleted: bool) -> list[dict[str, Any]]:
    cur.execute(
        f"""
        SELECT {_LIGHT_COLUMNS} FROM note_management.parts
        WHERE user_id = %s AND file_id = %s AND (%s OR NOT is_deleted)
        ORDER BY sort_order ASC, id ASC
        """,
        (user_id, file_id, include_deleted),
    )
    return [dict(row) for row in cur.fetchall()]


def next_sort_order(cur: PgCursor, user_id: int, file_id: int) -> int:
    cur.execute(
        "SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM note_management.parts "
        "WHERE user_id = %s AND file_id = %s",
        (user_id, file_id),
    )
    return int(cur.fetchone()["n"])


def insert_part(
    cur: PgCursor,
    user_id: int,
    file_id: int,
    sort_order: int,
    *,
    ptype: str,
    data: str,
    byte_size: int,
    filename: str,
    title: str,
    markers: list[dict[str, Any]],
    image_scale: float,
) -> int:
    cur.execute(
        """
        INSERT INTO note_management.parts
            (user_id, file_id, sort_order, ptype, data, byte_size, filename, title, markers, image_scale)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s) RETURNING id
        """,
        (
            user_id, file_id, sort_order, ptype, data, byte_size, filename, title,
            json.dumps(markers, ensure_ascii=False), image_scale,
        ),
    )
    return int(cur.fetchone()["id"])


def update_part(
    cur: PgCursor,
    part_id: int,
    *,
    ptype: str,
    data: str | None,
    byte_size: int | None,
    filename: str,
    title: str,
    markers: list[dict[str, Any]],
    image_scale: float,
) -> None:
    """data・byte_size は None のとき変更しない（大きな中身を送り直さない）。"""
    cur.execute(
        """
        UPDATE note_management.parts SET
            ptype = %s,
            data = COALESCE(%s, data),
            byte_size = COALESCE(%s, byte_size),
            filename = %s, title = %s, markers = %s::jsonb, image_scale = %s
        WHERE id = %s
        """,
        (ptype, data, byte_size, filename, title, json.dumps(markers, ensure_ascii=False), image_scale, part_id),
    )


def data_equals(cur: PgCursor, part_id: int, data: str) -> bool:
    cur.execute("SELECT data = %s AS same FROM note_management.parts WHERE id = %s", (data, part_id))
    return bool(cur.fetchone()["same"])


def data_prefix(cur: PgCursor, part_id: int, length: int = 32) -> str:
    """中身（Base64）の先頭。形式の確認に使う（中身の全体は読まない）。"""
    cur.execute("SELECT left(data, %s) AS head FROM note_management.parts WHERE id = %s", (length, part_id))
    return str(cur.fetchone()["head"])


def get_text_data(cur: PgCursor, part_id: int) -> str:
    cur.execute("SELECT data FROM note_management.parts WHERE id = %s", (part_id,))
    return str(cur.fetchone()["data"])


def set_deleted(cur: PgCursor, part_id: int, deleted: bool) -> None:
    cur.execute("UPDATE note_management.parts SET is_deleted = %s WHERE id = %s", (deleted, part_id))


def set_sort_order(cur: PgCursor, part_id: int, sort_order: int) -> None:
    cur.execute("UPDATE note_management.parts SET sort_order = %s WHERE id = %s", (sort_order, part_id))


def get_content(cur: PgCursor, user_id: int, part_id: int) -> dict[str, Any] | None:
    """画像・バイナリのパーツの中身。それ以外の種別は None。"""
    cur.execute(
        """
        SELECT ptype, filename, data FROM note_management.parts
        WHERE id = %s AND user_id = %s AND ptype IN ('jpeg', 'png', 'binary')
        """,
        (part_id, user_id),
    )
    row = cur.fetchone()
    return dict(row) if row is not None else None


# ---- 過去世代 ---------------------------------------------------------------


def snapshot_revision(cur: PgCursor, user_id: int, part_id: int) -> None:
    """現在の内容を、過去世代として保管する（中身はデータベースの中で複写する）。"""
    cur.execute(
        """
        INSERT INTO note_management.part_revisions
            (user_id, part_id, revision_number, ptype, filename, data, byte_size)
        SELECT p.user_id, p.id,
               COALESCE((SELECT MAX(r.revision_number) FROM note_management.part_revisions r
                         WHERE r.part_id = p.id), 0) + 1,
               p.ptype, p.filename, p.data, p.byte_size
        FROM note_management.parts p WHERE p.id = %s AND p.user_id = %s
        """,
        (part_id, user_id),
    )


def prune_revisions(cur: PgCursor, part_id: int, keep: int) -> None:
    """世代番号の大きいものから keep 件を残し、古い世代を削除する。"""
    cur.execute(
        """
        DELETE FROM note_management.part_revisions
        WHERE part_id = %s AND id NOT IN (
            SELECT id FROM note_management.part_revisions
            WHERE part_id = %s ORDER BY revision_number DESC LIMIT %s
        )
        """,
        (part_id, part_id, keep),
    )


def list_revisions(cur: PgCursor, part_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    result: dict[int, list[dict[str, Any]]] = {pid: [] for pid in part_ids}
    if not part_ids:
        return result
    cur.execute(
        """
        SELECT id, part_id, revision_number, ptype, filename, byte_size, created_at
        FROM note_management.part_revisions
        WHERE part_id = ANY(%s) ORDER BY part_id, revision_number DESC
        """,
        (part_ids,),
    )
    for row in cur.fetchall():
        result[row["part_id"]].append(dict(row))
    return result


def get_revision_content(cur: PgCursor, user_id: int, revision_id: int) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT ptype, filename, data FROM note_management.part_revisions
        WHERE id = %s AND user_id = %s
        """,
        (revision_id, user_id),
    )
    row = cur.fetchone()
    return dict(row) if row is not None else None


# ---- チェックリストとの紐づけ -----------------------------------------------


def insert_checklist(cur: PgCursor, user_id: int, part_id: int) -> int:
    cur.execute(
        "INSERT INTO note_management.checklists (user_id, part_id) VALUES (%s, %s) RETURNING id",
        (user_id, part_id),
    )
    return int(cur.fetchone()["id"])


def checklist_ids(cur: PgCursor, part_ids: list[int]) -> dict[int, int]:
    if not part_ids:
        return {}
    cur.execute(
        "SELECT part_id, id FROM note_management.checklists WHERE part_id = ANY(%s)",
        (part_ids,),
    )
    return {row["part_id"]: row["id"] for row in cur.fetchall()}
