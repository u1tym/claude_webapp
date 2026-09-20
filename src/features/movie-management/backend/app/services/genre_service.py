from __future__ import annotations

from typing import Any

from psycopg2 import errors

from app.db import get_conn
from app.errors import ConflictError
from app.logger import write
from app.repos import genre as genre_repo


def list_genres(user_id: int) -> dict[str, Any]:
    with get_conn() as conn, conn.cursor() as cur:
        items = genre_repo.list_genres(cur, user_id)
    write("INF", f"ジャンル一覧 user_id={user_id} 件数={len(items)}")
    return {"items": items}


def create_genre(user_id: int, name: str, sort_order: int) -> dict[str, Any]:
    write("INF", f"ジャンル追加要求 user_id={user_id} name={name} sort_order={sort_order}")
    try:
        with get_conn() as conn, conn.cursor() as cur:
            item = genre_repo.insert_genre(cur, user_id, name, sort_order)
    except errors.UniqueViolation:
        raise ConflictError("同じ名前のジャンルがあります", reason=f"ジャンル名重複 name={name}") from None
    write("INF", f"ジャンル追加成功 user_id={user_id} genre_id={item['id']}")
    return item
