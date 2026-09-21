from __future__ import annotations

from typing import Any

from psycopg2 import errors

from app.db import get_conn
from app.errors import ConflictError, InvalidInputError
from app.logger import write
from app.repos import measurement as measurement_repo

DUPLICATE = "同じ分量名称があります"


def list_measurements(user_id: int) -> dict[str, Any]:
    with get_conn() as conn, conn.cursor() as cur:
        items = measurement_repo.list_measurements(cur, user_id)
    write("INF", f"分量名称一覧 user_id={user_id} 件数={len(items)}")
    return {"items": items}


def create_measurement(user_id: int, name_bef: str, name_aft: str, ness_amount: bool) -> dict[str, Any]:
    write("INF", f"分量名称追加要求 user_id={user_id} 接頭語={name_bef} 接尾語={name_aft} 数量必要={ness_amount}")
    if not name_bef and not name_aft:
        raise InvalidInputError(reason="接頭語と接尾語が両方空")
    try:
        with get_conn() as conn, conn.cursor() as cur:
            if measurement_repo.pair_exists(cur, user_id, name_bef, name_aft):
                raise ConflictError(DUPLICATE, reason=f"分量名称重複 {name_bef}/{name_aft}")
            item = measurement_repo.insert_measurement(cur, user_id, name_bef, name_aft, ness_amount)
    except errors.UniqueViolation:
        raise ConflictError(DUPLICATE, reason=f"分量名称重複（同時の登録） {name_bef}/{name_aft}") from None
    write("INF", f"分量名称追加成功 user_id={user_id} measurement_id={item['id']}")
    return item
