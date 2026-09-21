"""フォルダとツリーの一覧の業務ロジック（design.md「フォルダ・ファイル」「ツリーの一覧」）。"""

from __future__ import annotations

from typing import Any

import psycopg2.errors

from app.db import get_conn
from app.errors import ConflictError, InvalidInputError, NotFoundError
from app.logger import write
from app.repos import file as file_repo
from app.repos import folder as repo

DELETED_MESSAGE = "削除済みのため操作できません"
SAME_NAME_MESSAGE = "同じ名前があります"


def is_name_conflict(exc: psycopg2.errors.UniqueViolation) -> bool:
    """名前（タイトル）の一意制約の違反か。並び順の一意制約の違反と区別する。"""
    name = exc.diag.constraint_name or ""
    return name.endswith("_name_uidx") or name.endswith("_title_uidx")


def folder_out(row: dict[str, Any], ancestor_deleted: bool) -> dict[str, Any]:
    return {
        "id": row["id"],
        "parent_id": row["parent_id"],
        "name": row["name"],
        "sort_order": row["sort_order"],
        "is_deleted": row["is_deleted"],
        "ancestor_deleted": ancestor_deleted,
    }


def file_out(row: dict[str, Any], ancestor_deleted: bool) -> dict[str, Any]:
    return {
        "id": row["id"],
        "folder_id": row["folder_id"],
        "title": row["title"],
        "sort_order": row["sort_order"],
        "is_deleted": row["is_deleted"],
        "ancestor_deleted": ancestor_deleted,
    }


def _require_folder(cur, user_id: int, folder_id: int, what: str = "フォルダ") -> dict[str, Any]:
    row = repo.get_folder(cur, user_id, folder_id)
    if row is None:
        raise NotFoundError(reason=f"{what}なし user_id={user_id} folder_id={folder_id}")
    return row


def list_items(user_id: int, folder_id: int | None, include_deleted: bool) -> dict[str, Any]:
    write("INF", f"一覧取得要求 user_id={user_id} folder_id={folder_id} include_deleted={include_deleted}")
    with get_conn() as conn, conn.cursor() as cur:
        parent = None
        children_deleted = False
        if folder_id is not None:
            row = _require_folder(cur, user_id, folder_id)
            parent_ancestors = repo.ancestors_deleted(cur, row["parent_id"])
            parent = {
                "id": row["id"],
                "name": row["name"],
                "is_deleted": row["is_deleted"],
                "ancestor_deleted": parent_ancestors,
            }
            children_deleted = row["is_deleted"] or parent_ancestors
        folders = [folder_out(r, children_deleted) for r in repo.list_children(cur, user_id, folder_id)]
        files = (
            [file_out(r, children_deleted) for r in file_repo.list_files(cur, user_id, folder_id)]
            if folder_id is not None
            else []
        )
        if not include_deleted:
            folders = [f for f in folders if not (f["is_deleted"] or f["ancestor_deleted"])]
            files = [f for f in files if not (f["is_deleted"] or f["ancestor_deleted"])]
    write("INF", f"一覧取得成功 user_id={user_id} folder_id={folder_id} フォルダ={len(folders)} ファイル={len(files)}")
    return {"parent": parent, "folders": folders, "files": files}


def create_folder(user_id: int, parent_id: int | None, name: str) -> dict[str, Any]:
    write("INF", f"フォルダ作成要求 user_id={user_id} parent_id={parent_id} name={name}")
    with get_conn() as conn, conn.cursor() as cur:
        if parent_id is not None:
            _require_folder(cur, user_id, parent_id, "親フォルダ")
            if repo.chain_deleted(cur, parent_id):
                raise ConflictError(DELETED_MESSAGE, reason=f"削除済みの親 parent_id={parent_id}")
        repo.lock_siblings(cur, user_id, parent_id)
        try:
            row = repo.insert_folder(cur, user_id, parent_id, name, repo.next_sort_order(cur, user_id, parent_id))
        except psycopg2.errors.UniqueViolation as exc:
            if is_name_conflict(exc):
                raise ConflictError(SAME_NAME_MESSAGE, reason=f"フォルダ名重複 name={name}") from exc
            raise
        out = folder_out(row, repo.ancestors_deleted(cur, parent_id))
    write("INF", f"フォルダ作成成功 user_id={user_id} folder_id={out['id']}")
    return out


def rename_folder(user_id: int, folder_id: int, name: str) -> dict[str, Any]:
    write("INF", f"フォルダ名変更要求 user_id={user_id} folder_id={folder_id} name={name}")
    with get_conn() as conn, conn.cursor() as cur:
        row = _require_folder(cur, user_id, folder_id)
        if repo.chain_deleted(cur, folder_id):
            raise ConflictError(DELETED_MESSAGE, reason=f"削除済み folder_id={folder_id}")
        try:
            row = repo.rename_folder(cur, folder_id, name)
        except psycopg2.errors.UniqueViolation as exc:
            if is_name_conflict(exc):
                raise ConflictError(SAME_NAME_MESSAGE, reason=f"フォルダ名重複 name={name}") from exc
            raise
        out = folder_out(row, repo.ancestors_deleted(cur, row["parent_id"]))
    write("INF", f"フォルダ名変更成功 user_id={user_id} folder_id={folder_id}")
    return out


def move_folder(user_id: int, folder_id: int, new_parent_id: int | None) -> dict[str, Any]:
    write("INF", f"フォルダ移動要求 user_id={user_id} folder_id={folder_id} new_parent_id={new_parent_id}")
    with get_conn() as conn, conn.cursor() as cur:
        row = _require_folder(cur, user_id, folder_id)
        if new_parent_id is not None:
            _require_folder(cur, user_id, new_parent_id, "移動先")
        if repo.chain_deleted(cur, folder_id) or (
            new_parent_id is not None and repo.chain_deleted(cur, new_parent_id)
        ):
            raise ConflictError(DELETED_MESSAGE, reason=f"削除済み folder_id={folder_id} new_parent_id={new_parent_id}")
        if new_parent_id is not None and repo.is_self_or_descendant(cur, folder_id, new_parent_id):
            raise ConflictError("自分の中には移動できません", reason=f"自身・子孫への移動 folder_id={folder_id}")
        if new_parent_id == row["parent_id"]:
            raise ConflictError("現在の場所と同じです", reason=f"移動先が現在の親 folder_id={folder_id}")
        repo.lock_siblings(cur, user_id, new_parent_id)
        try:
            moved = repo.move_folder(cur, folder_id, new_parent_id, repo.next_sort_order(cur, user_id, new_parent_id))
        except psycopg2.errors.UniqueViolation as exc:
            if is_name_conflict(exc):
                raise ConflictError(SAME_NAME_MESSAGE, reason=f"移動先に同名 name={row['name']}") from exc
            raise
        out = folder_out(moved, repo.ancestors_deleted(cur, new_parent_id))
    write("INF", f"フォルダ移動成功 user_id={user_id} folder_id={folder_id}")
    return out


def swap_order(user_id: int, folder_id_1: int, folder_id_2: int) -> None:
    write("INF", f"フォルダ並び替え要求 user_id={user_id} folder_id_1={folder_id_1} folder_id_2={folder_id_2}")
    if folder_id_1 == folder_id_2:
        raise InvalidInputError(reason="同じフォルダの入れ替え")
    with get_conn() as conn, conn.cursor() as cur:
        a = _require_folder(cur, user_id, folder_id_1)
        b = _require_folder(cur, user_id, folder_id_2)
        if a["parent_id"] != b["parent_id"]:
            raise InvalidInputError("同じ場所の項目ではありません", reason="親が違う")
        if repo.chain_deleted(cur, folder_id_1) or repo.chain_deleted(cur, folder_id_2):
            raise ConflictError(DELETED_MESSAGE, reason="削除済みの入れ替え")
        repo.lock_siblings(cur, user_id, a["parent_id"])
        # 並び順は一意のため、未使用の値（-1）を経由して交換する
        repo.set_sort_order(cur, folder_id_1, -1)
        repo.set_sort_order(cur, folder_id_2, a["sort_order"])
        repo.set_sort_order(cur, folder_id_1, b["sort_order"])
    write("INF", f"フォルダ並び替え成功 user_id={user_id}")


def delete_folder(user_id: int, folder_id: int) -> None:
    write("INF", f"フォルダ削除要求 user_id={user_id} folder_id={folder_id}")
    with get_conn() as conn, conn.cursor() as cur:
        row = _require_folder(cur, user_id, folder_id)
        if row["is_deleted"]:
            raise ConflictError("既に削除されています", reason=f"削除済み folder_id={folder_id}")
        repo.set_deleted(cur, folder_id, True)
    write("INF", f"フォルダ削除成功 user_id={user_id} folder_id={folder_id}")


def undelete_folder(user_id: int, folder_id: int) -> dict[str, Any]:
    write("INF", f"フォルダ削除解除要求 user_id={user_id} folder_id={folder_id}")
    with get_conn() as conn, conn.cursor() as cur:
        row = _require_folder(cur, user_id, folder_id)
        if not row["is_deleted"]:
            raise ConflictError("削除されていません", reason=f"削除済みでない folder_id={folder_id}")
        try:
            # 並び順は、削除済みを含めて一意のため、元の位置のまま戻せる（重なることはない）
            restored = repo.set_deleted(cur, folder_id, False)
        except psycopg2.errors.UniqueViolation as exc:
            if is_name_conflict(exc):
                raise ConflictError(SAME_NAME_MESSAGE, reason=f"削除解除で同名 name={row['name']}") from exc
            raise
        out = folder_out(restored, repo.ancestors_deleted(cur, restored["parent_id"]))
    write("INF", f"フォルダ削除解除成功 user_id={user_id} folder_id={folder_id}")
    return out
