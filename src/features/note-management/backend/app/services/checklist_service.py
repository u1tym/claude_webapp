"""チェックリストの業務ロジック（design.md「チェックリスト」）。変更の操作は、変更後の状態を返す。"""

from __future__ import annotations

from typing import Any

import psycopg2.errors

from app.db import get_conn
from app.errors import ConflictError, InvalidInputError, NotFoundError
from app.logger import write
from app.repos import checklist as repo
from app.services.file_service import file_effective_deleted, require_file
from app.services.folder_service import DELETED_MESSAGE

SAME_CATEGORY_MESSAGE = "同じ名前のカテゴリがあります"


def _state(cur, checklist: dict[str, Any]) -> dict[str, Any]:
    items_by_category: dict[int, list[dict[str, Any]]] = {}
    for item in repo.live_items(cur, checklist["id"]):
        items_by_category.setdefault(item["category_id"], []).append(
            {"id": item["id"], "title": item["title"], "is_checked": item["is_checked"]}
        )
    return {
        "checklist_id": checklist["id"],
        "title": checklist["title"],
        "categories": [
            {
                "id": c["id"],
                "name": c["name"],
                "is_unnamed": c["name"] == "",
                "items": items_by_category.get(c["id"], []),
            }
            for c in repo.live_categories(cur, checklist["id"])
        ],
    }


def _require(cur, user_id: int, checklist_id: int, *, for_update: bool) -> dict[str, Any]:
    checklist = repo.get_checklist(cur, user_id, checklist_id, lock=for_update)
    if checklist is None:
        raise NotFoundError(reason=f"チェックリストなし user_id={user_id} checklist_id={checklist_id}")
    if for_update:
        # パーツ・所属ファイルが削除済み（上位を含む）のときは、変更できない
        file_row = require_file(cur, user_id, checklist["file_id"])
        if checklist["part_deleted"] or file_effective_deleted(cur, file_row):
            raise ConflictError(DELETED_MESSAGE, reason=f"削除済みのチェックリスト checklist_id={checklist_id}")
    return checklist


def _category(cur, checklist_id: int, category_id: int) -> dict[str, Any]:
    category = repo.get_live_category(cur, checklist_id, category_id)
    if category is None:
        raise NotFoundError(reason=f"カテゴリなし checklist_id={checklist_id} category_id={category_id}")
    return category


def _item(cur, checklist_id: int, item_id: int) -> dict[str, Any]:
    item = repo.get_live_item(cur, checklist_id, item_id)
    if item is None:
        raise NotFoundError(reason=f"項目なし checklist_id={checklist_id} item_id={item_id}")
    return item


def _conflict_of(exc: psycopg2.errors.UniqueViolation, name: str) -> ConflictError:
    if (exc.diag.constraint_name or "") == "checklist_categories_name_uidx":
        return ConflictError(SAME_CATEGORY_MESSAGE, reason=f"カテゴリ名重複 name={name}")
    raise exc


def get_checklist(user_id: int, checklist_id: int) -> dict[str, Any]:
    write("INF", f"チェックリスト取得要求 user_id={user_id} checklist_id={checklist_id}")
    with get_conn() as conn, conn.cursor() as cur:
        checklist = _require(cur, user_id, checklist_id, for_update=False)
        out = _state(cur, checklist)
    write("INF", f"チェックリスト取得成功 user_id={user_id} checklist_id={checklist_id} カテゴリ={len(out['categories'])}")
    return out


def update_title(user_id: int, checklist_id: int, title: str) -> dict[str, Any]:
    write("INF", f"チェックリストのタイトル変更要求 user_id={user_id} checklist_id={checklist_id}")
    with get_conn() as conn, conn.cursor() as cur:
        checklist = _require(cur, user_id, checklist_id, for_update=True)
        repo.set_title(cur, checklist_id, title)
        checklist["title"] = title
        out = _state(cur, checklist)
    write("INF", f"チェックリストのタイトル変更成功 user_id={user_id} checklist_id={checklist_id}")
    return out


def create_category(user_id: int, checklist_id: int, name: str) -> dict[str, Any]:
    write("INF", f"カテゴリ追加要求 user_id={user_id} checklist_id={checklist_id} name={name}")
    with get_conn() as conn, conn.cursor() as cur:
        checklist = _require(cur, user_id, checklist_id, for_update=True)
        try:
            repo.insert_category(cur, checklist_id, name)
        except psycopg2.errors.UniqueViolation as exc:
            raise _conflict_of(exc, name) from exc
        out = _state(cur, checklist)
    write("INF", f"カテゴリ追加成功 user_id={user_id} checklist_id={checklist_id}")
    return out


def rename_category(user_id: int, checklist_id: int, category_id: int, name: str) -> dict[str, Any]:
    write("INF", f"カテゴリ名変更要求 user_id={user_id} checklist_id={checklist_id} category_id={category_id} name={name}")
    with get_conn() as conn, conn.cursor() as cur:
        checklist = _require(cur, user_id, checklist_id, for_update=True)
        category = _category(cur, checklist_id, category_id)
        if category["name"] == "":
            raise ConflictError("無名のカテゴリは変更できません", reason=f"無名カテゴリの名前変更 category_id={category_id}")
        try:
            repo.rename_category(cur, category_id, name)
        except psycopg2.errors.UniqueViolation as exc:
            raise _conflict_of(exc, name) from exc
        out = _state(cur, checklist)
    write("INF", f"カテゴリ名変更成功 user_id={user_id} checklist_id={checklist_id} category_id={category_id}")
    return out


def delete_category(user_id: int, checklist_id: int, category_id: int) -> dict[str, Any]:
    write("INF", f"カテゴリ削除要求 user_id={user_id} checklist_id={checklist_id} category_id={category_id}")
    with get_conn() as conn, conn.cursor() as cur:
        checklist = _require(cur, user_id, checklist_id, for_update=True)
        _category(cur, checklist_id, category_id)
        repo.delete_category(cur, category_id)  # 中の項目も論理削除する
        out = _state(cur, checklist)
    write("INF", f"カテゴリ削除成功 user_id={user_id} checklist_id={checklist_id} category_id={category_id}")
    return out


def reorder_categories(user_id: int, checklist_id: int, ordered_ids: list[int]) -> dict[str, Any]:
    write("INF", f"カテゴリ並び替え要求 user_id={user_id} checklist_id={checklist_id} 件数={len(ordered_ids)}")
    if len(set(ordered_ids)) != len(ordered_ids):
        raise InvalidInputError(reason="ordered_ids に重複")
    with get_conn() as conn, conn.cursor() as cur:
        checklist = _require(cur, user_id, checklist_id, for_update=True)
        named = [c["id"] for c in repo.live_categories(cur, checklist_id) if c["name"] != ""]
        if sorted(named) != sorted(ordered_ids):
            raise InvalidInputError("カテゴリの並びが正しくありません", reason=f"カテゴリの集合が違う 期待={sorted(named)}")
        for index, category_id in enumerate(ordered_ids, start=1):
            repo.set_category_order(cur, category_id, index)
        out = _state(cur, checklist)
    write("INF", f"カテゴリ並び替え成功 user_id={user_id} checklist_id={checklist_id}")
    return out


def create_item(user_id: int, checklist_id: int, category_id: int | None, title: str) -> dict[str, Any]:
    write("INF", f"項目追加要求 user_id={user_id} checklist_id={checklist_id} category_id={category_id}")
    with get_conn() as conn, conn.cursor() as cur:
        checklist = _require(cur, user_id, checklist_id, for_update=True)
        if category_id is None:
            unnamed = repo.get_unnamed_category(cur, checklist_id)
            target = unnamed["id"] if unnamed else repo.insert_category(cur, checklist_id, "", 0)
        else:
            target = _category(cur, checklist_id, category_id)["id"]
        repo.insert_item(cur, checklist_id, target, title)
        out = _state(cur, checklist)
    write("INF", f"項目追加成功 user_id={user_id} checklist_id={checklist_id}")
    return out


def update_item(user_id: int, checklist_id: int, item_id: int, title: str | None, is_checked: bool | None) -> dict[str, Any]:
    write("INF", f"項目更新要求 user_id={user_id} checklist_id={checklist_id} item_id={item_id} is_checked={is_checked}")
    if title is None and is_checked is None:
        raise InvalidInputError(reason="更新する項目がない")
    with get_conn() as conn, conn.cursor() as cur:
        checklist = _require(cur, user_id, checklist_id, for_update=True)
        _item(cur, checklist_id, item_id)
        repo.update_item(cur, item_id, title, is_checked)
        out = _state(cur, checklist)
    write("INF", f"項目更新成功 user_id={user_id} checklist_id={checklist_id} item_id={item_id}")
    return out


def delete_item(user_id: int, checklist_id: int, item_id: int) -> dict[str, Any]:
    write("INF", f"項目削除要求 user_id={user_id} checklist_id={checklist_id} item_id={item_id}")
    with get_conn() as conn, conn.cursor() as cur:
        checklist = _require(cur, user_id, checklist_id, for_update=True)
        _item(cur, checklist_id, item_id)
        repo.delete_item(cur, item_id)
        out = _state(cur, checklist)
    write("INF", f"項目削除成功 user_id={user_id} checklist_id={checklist_id} item_id={item_id}")
    return out


def move_item(user_id: int, checklist_id: int, item_id: int, to_category_id: int, to_index: int) -> dict[str, Any]:
    write(
        "INF",
        f"項目移動要求 user_id={user_id} checklist_id={checklist_id} item_id={item_id} to_category_id={to_category_id} to_index={to_index}",
    )
    with get_conn() as conn, conn.cursor() as cur:
        checklist = _require(cur, user_id, checklist_id, for_update=True)
        item = _item(cur, checklist_id, item_id)
        _category(cur, checklist_id, to_category_id)
        source_id = item["category_id"]
        target_ids = [i for i in repo.category_items(cur, to_category_id) if i != item_id]
        target_ids.insert(min(to_index, len(target_ids)), item_id)
        repo.place_items(cur, to_category_id, target_ids)
        if source_id != to_category_id:
            repo.place_items(cur, source_id, [i for i in repo.category_items(cur, source_id)])
        out = _state(cur, checklist)
    write("INF", f"項目移動成功 user_id={user_id} checklist_id={checklist_id} item_id={item_id}")
    return out
