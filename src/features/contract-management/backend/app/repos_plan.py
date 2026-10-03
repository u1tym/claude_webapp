"""解約順（cancellation_plan）のデータアクセス。"""

from __future__ import annotations

from psycopg2.extensions import connection as PgConnection

# 解約の対象にできる契約の条件（契約を伴う契約で、ステータスが有効または休止中、削除されていない）
ELIGIBLE = "c.is_deleted = false AND c.has_contract = true AND c.status IN ('active', 'paused')"


def list_plan_rows(conn: PgConnection, user_id: int) -> list[dict[str, object]]:
    """解約順（`position` の昇順）。対象としての条件を満たさなくなった契約は含めない。"""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT c.id AS contract_id, c.name, c.cancellation_method
            FROM contract_management.cancellation_plan p
            JOIN contract_management.contracts c ON c.id = p.contract_id
            WHERE p.user_id = %s AND c.user_id = %s AND {ELIGIBLE}
            ORDER BY p.position, c.id
            """,
            (user_id, user_id),
        )
        return [dict(r) for r in cur.fetchall()]


def dependency_names(conn: PgConnection, contract_ids: list[int]) -> dict[int, list[dict[str, object]]]:
    """契約ごとの依存契約（削除されていないもの）。{契約 ID: [{id, name}]}（依存先の ID 昇順）。"""
    result: dict[int, list[dict[str, object]]] = {i: [] for i in contract_ids}
    if not contract_ids:
        return result
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.contract_id AS owner_id, t.id AS rel_id, t.name AS rel_name
            FROM contract_management.contract_dependencies d
            JOIN contract_management.contracts t ON t.id = d.depends_on_contract_id
            WHERE d.contract_id = ANY(%s) AND t.is_deleted = false
            ORDER BY d.contract_id, t.id
            """,
            (contract_ids,),
        )
        for r in cur.fetchall():
            result[int(r["owner_id"])].append({"id": int(r["rel_id"]), "name": str(r["rel_name"])})
    return result


def list_candidates(conn: PgConnection, user_id: int) -> list[dict[str, object]]:
    """解約の対象にできて、まだ解約順に入っていない契約（ID 昇順）。"""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT c.id, c.name, g.name AS category_name,
                   (c.cancellation_method IS NOT NULL) AS has_cancellation_method
            FROM contract_management.contracts c
            JOIN contract_management.categories g ON g.id = c.category_id
            WHERE c.user_id = %s AND {ELIGIBLE}
              AND NOT EXISTS (
                  SELECT 1 FROM contract_management.cancellation_plan p
                  WHERE p.user_id = c.user_id AND p.contract_id = c.id
              )
            ORDER BY c.id
            """,
            (user_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def count_eligible(conn: PgConnection, user_id: int, contract_ids: list[int]) -> int:
    """指定した ID のうち、本人の、解約の対象にできる契約の数。"""
    if not contract_ids:
        return 0
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT count(*) AS n
            FROM contract_management.contracts c
            WHERE c.user_id = %s AND c.id = ANY(%s) AND {ELIGIBLE}
            """,
            (user_id, contract_ids),
        )
        return int(cur.fetchone()["n"])


def replace_plan(conn: PgConnection, user_id: int, contract_ids: list[int]) -> None:
    """利用者の解約順を、指定した順に置き換える（`position` は 1 からの連番）。

    `(user_id, position)` の一意制約は、トランザクションの終わりまで検査を遅らせている。
    """
    with conn.cursor() as cur:
        cur.execute("DELETE FROM contract_management.cancellation_plan WHERE user_id = %s", (user_id,))
        for position, contract_id in enumerate(contract_ids, start=1):
            cur.execute(
                "INSERT INTO contract_management.cancellation_plan (user_id, contract_id, position) "
                "VALUES (%s, %s, %s)",
                (user_id, contract_id, position),
            )
