from __future__ import annotations

from dataclasses import asdict

import psycopg2.errors

from app import repos
from app.common import required_text
from app.db import get_conn
from app.errors import ConflictError, InvalidInputError, NotFoundError
from app.logger import write
from app.repos import CategoryRow

NAME_MAX = 100


def _to_dict(row: CategoryRow) -> dict[str, object]:
    d = asdict(row)
    return {"id": d["id"], "name": d["name"], "is_default": d["is_default"], "is_financial": d["is_financial"]}


def list_categories(user_id: int) -> list[dict[str, object]]:
    with get_conn() as conn:
        repos.ensure_default_category(conn, user_id)
        rows = repos.list_categories(conn, user_id)
    write("INF", f"区分一覧 user_id={user_id} 件数={len(rows)}")
    return [_to_dict(r) for r in rows]


def create_category(user_id: int, name: object, is_financial: bool) -> dict[str, object]:
    write("INF", f"区分追加要求 user_id={user_id} name={name!r} is_financial={is_financial}")
    try:
        clean = required_text(name, NAME_MAX)
    except InvalidInputError as exc:
        raise InvalidInputError(f"区分の名称が不正 {exc}") from exc
    with get_conn() as conn:
        repos.ensure_default_category(conn, user_id)
        if repos.category_name_exists(conn, user_id, clean):
            raise ConflictError(f"区分の名称が重複 name={clean!r}")
        try:
            row = repos.insert_category(conn, user_id, clean, is_financial)
        except psycopg2.errors.UniqueViolation as exc:
            raise ConflictError(f"区分の名称が重複 name={clean!r}") from exc
    write("INF", f"区分追加成功 user_id={user_id} id={row.id}")
    return _to_dict(row)


def update_category(user_id: int, category_id: int, name: object, is_financial: bool) -> dict[str, object]:
    write(
        "INF",
        f"区分更新要求 user_id={user_id} id={category_id} name={name!r} is_financial={is_financial}",
    )
    try:
        clean = required_text(name, NAME_MAX)
    except InvalidInputError as exc:
        raise InvalidInputError(f"区分の名称が不正 {exc}") from exc
    with get_conn() as conn:
        current = repos.get_category(conn, user_id, category_id, for_update=True)
        if current is None:
            raise NotFoundError(f"区分が本人の削除されていないものでない id={category_id}")
        if current.is_default:
            raise ConflictError(f"「その他」は変更できない id={category_id}")
        if repos.category_name_exists(conn, user_id, clean, exclude_id=category_id):
            raise ConflictError(f"区分の名称が重複 name={clean!r}")
        if current.is_financial and not is_financial and repos.category_used_as_payment(conn, category_id):
            raise ConflictError(f"支払方法として使われているため金融機関の指定を外せない id={category_id}")
        try:
            row = repos.update_category(conn, category_id, clean, is_financial)
        except psycopg2.errors.UniqueViolation as exc:
            raise ConflictError(f"区分の名称が重複 name={clean!r}") from exc
    write("INF", f"区分更新成功 user_id={user_id} id={category_id}")
    return _to_dict(row)


def delete_category(user_id: int, category_id: int) -> None:
    write("INF", f"区分削除要求 user_id={user_id} id={category_id}")
    with get_conn() as conn:
        current = repos.get_category(conn, user_id, category_id, for_update=True)
        if current is None:
            raise NotFoundError(f"区分が本人の削除されていないものでない id={category_id}")
        if current.is_default:
            raise ConflictError(f"「その他」は削除できない id={category_id}")
        if repos.category_in_use(conn, category_id):
            raise ConflictError(f"使用中の区分は削除できない id={category_id}")
        repos.soft_delete_category(conn, category_id)
    write("INF", f"区分削除成功 user_id={user_id} id={category_id}")
