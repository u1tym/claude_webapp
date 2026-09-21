from __future__ import annotations

from typing import Any

from psycopg2 import errors

from app.db import get_conn
from app.errors import ConflictError
from app.logger import write
from app.repos import ingredient as ingredient_repo

DUPLICATE = "同じ名前の材料があります"


def list_ingredients(user_id: int) -> dict[str, Any]:
    with get_conn() as conn, conn.cursor() as cur:
        items = ingredient_repo.list_ingredients(cur, user_id)
    write("INF", f"材料一覧 user_id={user_id} 件数={len(items)}")
    return {"items": items}


def create_ingredient(user_id: int, name: str, kana: str) -> dict[str, Any]:
    write("INF", f"材料追加要求 user_id={user_id} name={name} kana={kana}")
    try:
        with get_conn() as conn, conn.cursor() as cur:
            if ingredient_repo.name_exists(cur, user_id, name):
                raise ConflictError(DUPLICATE, reason=f"材料名重複 name={name}")
            item = ingredient_repo.insert_ingredient(cur, user_id, name, kana)
    except errors.UniqueViolation:
        raise ConflictError(DUPLICATE, reason=f"材料名重複（同時の登録） name={name}") from None
    write("INF", f"材料追加成功 user_id={user_id} ingredient_id={item['id']}")
    return item
