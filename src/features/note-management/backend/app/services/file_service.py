"""ファイル（パーツを除く）の業務ロジック（design.md「フォルダ・ファイル」）。"""

from __future__ import annotations

from typing import Any

import psycopg2.errors

from app.db import get_conn
from app.errors import ConflictError, InvalidInputError, NotFoundError
from app.logger import write
from app.repos import file as repo
from app.repos import folder as folder_repo
from app.services.folder_service import DELETED_MESSAGE, file_out, is_name_conflict

SAME_TITLE_MESSAGE = "同じタイトルがあります"


def require_file(cur, user_id: int, file_id: int) -> dict[str, Any]:
    row = repo.get_file(cur, user_id, file_id)
    if row is None:
        raise NotFoundError(reason=f"ファイルなし user_id={user_id} file_id={file_id}")
    return row


def file_effective_deleted(cur, file_row: dict[str, Any]) -> bool:
    """ファイル自身、または所属フォルダ・その上位が削除済みか。"""
    return bool(file_row["is_deleted"]) or folder_repo.chain_deleted(cur, file_row["folder_id"])


def _require_folder(cur, user_id: int, folder_id: int) -> dict[str, Any]:
    row = folder_repo.get_folder(cur, user_id, folder_id)
    if row is None:
        raise NotFoundError(reason=f"フォルダなし user_id={user_id} folder_id={folder_id}")
    return row


def create_file(user_id: int, folder_id: int, title: str) -> dict[str, Any]:
    write("INF", f"ファイル作成要求 user_id={user_id} folder_id={folder_id} title={title}")
    with get_conn() as conn, conn.cursor() as cur:
        _require_folder(cur, user_id, folder_id)
        if folder_repo.chain_deleted(cur, folder_id):
            raise ConflictError(DELETED_MESSAGE, reason=f"削除済みのフォルダ folder_id={folder_id}")
        folder_repo.lock_siblings(cur, user_id, folder_id)
        try:
            row = repo.insert_file(cur, user_id, folder_id, title, repo.next_sort_order(cur, user_id, folder_id))
        except psycopg2.errors.UniqueViolation as exc:
            if is_name_conflict(exc):
                raise ConflictError(SAME_TITLE_MESSAGE, reason=f"ファイル名重複 title={title}") from exc
            raise
        out = file_out(row, False)
    write("INF", f"ファイル作成成功 user_id={user_id} file_id={out['id']}")
    return out


def rename_file(user_id: int, file_id: int, title: str) -> dict[str, Any]:
    write("INF", f"ファイル名変更要求 user_id={user_id} file_id={file_id} title={title}")
    with get_conn() as conn, conn.cursor() as cur:
        row = require_file(cur, user_id, file_id)
        if file_effective_deleted(cur, row):
            raise ConflictError(DELETED_MESSAGE, reason=f"削除済み file_id={file_id}")
        try:
            row = repo.rename_file(cur, file_id, title)
        except psycopg2.errors.UniqueViolation as exc:
            if is_name_conflict(exc):
                raise ConflictError(SAME_TITLE_MESSAGE, reason=f"ファイル名重複 title={title}") from exc
            raise
        out = file_out(row, folder_repo.chain_deleted(cur, row["folder_id"]))
    write("INF", f"ファイル名変更成功 user_id={user_id} file_id={file_id}")
    return out


def move_file(user_id: int, file_id: int, new_folder_id: int) -> dict[str, Any]:
    write("INF", f"ファイル移動要求 user_id={user_id} file_id={file_id} new_folder_id={new_folder_id}")
    with get_conn() as conn, conn.cursor() as cur:
        row = require_file(cur, user_id, file_id)
        _require_folder(cur, user_id, new_folder_id)
        if file_effective_deleted(cur, row) or folder_repo.chain_deleted(cur, new_folder_id):
            raise ConflictError(DELETED_MESSAGE, reason=f"削除済み file_id={file_id} new_folder_id={new_folder_id}")
        if new_folder_id == row["folder_id"]:
            raise ConflictError("現在の場所と同じです", reason=f"移動先が現在のフォルダ file_id={file_id}")
        folder_repo.lock_siblings(cur, user_id, new_folder_id)
        try:
            moved = repo.move_file(cur, file_id, new_folder_id, repo.next_sort_order(cur, user_id, new_folder_id))
        except psycopg2.errors.UniqueViolation as exc:
            if is_name_conflict(exc):
                raise ConflictError(SAME_TITLE_MESSAGE, reason=f"移動先に同タイトル title={row['title']}") from exc
            raise
        out = file_out(moved, False)
    write("INF", f"ファイル移動成功 user_id={user_id} file_id={file_id}")
    return out


def swap_order(user_id: int, file_id_1: int, file_id_2: int) -> None:
    write("INF", f"ファイル並び替え要求 user_id={user_id} file_id_1={file_id_1} file_id_2={file_id_2}")
    if file_id_1 == file_id_2:
        raise InvalidInputError(reason="同じファイルの入れ替え")
    with get_conn() as conn, conn.cursor() as cur:
        a = require_file(cur, user_id, file_id_1)
        b = require_file(cur, user_id, file_id_2)
        if a["folder_id"] != b["folder_id"]:
            raise InvalidInputError("同じ場所の項目ではありません", reason="所属フォルダが違う")
        if file_effective_deleted(cur, a) or file_effective_deleted(cur, b):
            raise ConflictError(DELETED_MESSAGE, reason="削除済みの入れ替え")
        folder_repo.lock_siblings(cur, user_id, a["folder_id"])
        repo.set_sort_order(cur, file_id_1, -1)
        repo.set_sort_order(cur, file_id_2, a["sort_order"])
        repo.set_sort_order(cur, file_id_1, b["sort_order"])
    write("INF", f"ファイル並び替え成功 user_id={user_id}")


def delete_file(user_id: int, file_id: int) -> None:
    write("INF", f"ファイル削除要求 user_id={user_id} file_id={file_id}")
    with get_conn() as conn, conn.cursor() as cur:
        row = require_file(cur, user_id, file_id)
        if row["is_deleted"]:
            raise ConflictError("既に削除されています", reason=f"削除済み file_id={file_id}")
        repo.set_deleted(cur, file_id, True)
    write("INF", f"ファイル削除成功 user_id={user_id} file_id={file_id}")


def undelete_file(user_id: int, file_id: int) -> dict[str, Any]:
    write("INF", f"ファイル削除解除要求 user_id={user_id} file_id={file_id}")
    with get_conn() as conn, conn.cursor() as cur:
        row = require_file(cur, user_id, file_id)
        if not row["is_deleted"]:
            raise ConflictError("削除されていません", reason=f"削除済みでない file_id={file_id}")
        try:
            restored = repo.set_deleted(cur, file_id, False)
        except psycopg2.errors.UniqueViolation as exc:
            if is_name_conflict(exc):
                raise ConflictError(SAME_TITLE_MESSAGE, reason=f"削除解除で同タイトル title={row['title']}") from exc
            raise
        out = file_out(restored, folder_repo.chain_deleted(cur, restored["folder_id"]))
    write("INF", f"ファイル削除解除成功 user_id={user_id} file_id={file_id}")
    return out
