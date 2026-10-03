from __future__ import annotations

from psycopg2.extensions import connection as PgConnection

from app import repos_plan, repos_write
from app.db import get_conn
from app.errors import InvalidInputError
from app.logger import write


def _plan(conn: PgConnection, user_id: int) -> dict[str, object]:
    rows = repos_plan.list_plan_rows(conn, user_id)
    ids = [int(r["contract_id"]) for r in rows]  # type: ignore[arg-type]
    deps = repos_plan.dependency_names(conn, ids)
    position_of = {cid: pos for pos, cid in enumerate(ids, start=1)}
    items: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    for r in rows:
        cid = int(r["contract_id"])  # type: ignore[arg-type]
        items.append(
            {
                "position": position_of[cid],
                "contract_id": cid,
                "name": str(r["name"]),
                "cancellation_method": r["cancellation_method"],
                "depends_on": deps[cid],
            }
        )
        # 依存している契約が、この契約より先に解約順に並んでいるとき、警告にする
        for dep in deps[cid]:
            dep_id = int(dep["id"])  # type: ignore[arg-type]
            if dep_id in position_of and position_of[dep_id] < position_of[cid]:
                warnings.append(
                    {
                        "contract_id": cid,
                        "name": str(r["name"]),
                        "depends_on_contract_id": dep_id,
                        "depends_on_name": dep["name"],
                    }
                )
    return {"items": items, "warnings": warnings}


def get_plan(user_id: int) -> dict[str, object]:
    write("INF", f"解約順取得要求 user_id={user_id}")
    with get_conn() as conn:
        plan = _plan(conn, user_id)
    write(
        "INF",
        f"解約順取得成功 user_id={user_id} 件数={len(plan['items'])} 警告={len(plan['warnings'])}",  # type: ignore[arg-type]
    )
    return plan


def list_candidates(user_id: int) -> dict[str, object]:
    write("INF", f"解約順の候補取得要求 user_id={user_id}")
    with get_conn() as conn:
        rows = repos_plan.list_candidates(conn, user_id)
    items = [
        {
            "id": int(r["id"]),  # type: ignore[arg-type]
            "name": str(r["name"]),
            "category_name": str(r["category_name"]),
            "has_cancellation_method": bool(r["has_cancellation_method"]),
        }
        for r in rows
    ]
    write("INF", f"解約順の候補取得成功 user_id={user_id} 件数={len(items)}")
    return {"items": items}


def save_plan(user_id: int, contract_ids: list[int]) -> dict[str, object]:
    write("INF", f"解約順保存要求 user_id={user_id} contract_ids={contract_ids}")
    if len(set(contract_ids)) != len(contract_ids):
        raise InvalidInputError("解約順に同じ契約が重複している")
    with get_conn() as conn:
        repos_write.lock_user_contracts(conn, user_id)
        if repos_plan.count_eligible(conn, user_id, contract_ids) != len(contract_ids):
            raise InvalidInputError("解約の対象にできない契約が含まれている")
        repos_plan.replace_plan(conn, user_id, contract_ids)
        plan = _plan(conn, user_id)
    write(
        "INF",
        f"解約順保存成功 user_id={user_id} 件数={len(contract_ids)} 警告={len(plan['warnings'])}",  # type: ignore[arg-type]
    )
    return plan
