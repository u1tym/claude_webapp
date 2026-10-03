"""契約の書き込み系のデータアクセス（登録・更新・削除、依存契約、解約順からの除外）。"""

from __future__ import annotations

from dataclasses import dataclass

from psycopg2.extensions import connection as PgConnection

from app.contract_model import ContractData


@dataclass(frozen=True)
class ContractCurrent:
    id: int
    category_id: int
    category_is_financial: bool


def lock_user_contracts(conn: PgConnection, user_id: int) -> None:
    """利用者ごとに、契約の更新を直列にする（依存の循環の検査と更新の間に、他の更新が入らないように）。"""
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(%s, %s)", (4101, user_id))


def get_current(conn: PgConnection, user_id: int, contract_id: int) -> ContractCurrent | None:
    """本人の削除されていない契約を、行ロックして返す。無ければ None。"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.id, c.category_id, g.is_financial
            FROM contract_management.contracts c
            JOIN contract_management.categories g ON g.id = c.category_id
            WHERE c.id = %s AND c.user_id = %s AND c.is_deleted = false
            FOR UPDATE OF c
            """,
            (contract_id, user_id),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return ContractCurrent(
            id=int(row["id"]), category_id=int(row["category_id"]), category_is_financial=bool(row["is_financial"])
        )


def find_own_contracts(conn: PgConnection, user_id: int, ids: list[int]) -> dict[int, bool]:
    """指定した ID のうち、本人の削除されていない契約を、{ID: 区分が金融機関か} で返す。"""
    if not ids:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.id, g.is_financial
            FROM contract_management.contracts c
            JOIN contract_management.categories g ON g.id = c.category_id
            WHERE c.user_id = %s AND c.is_deleted = false AND c.id = ANY(%s)
            """,
            (user_id, ids),
        )
        return {int(r["id"]): bool(r["is_financial"]) for r in cur.fetchall()}


def dependency_reaches(conn: PgConnection, start_ids: list[int], target_id: int, skip_source_id: int) -> bool:
    """start_ids から「依存する先」をたどって、target_id に着くか。

    skip_source_id の契約が持つ依存（更新で置き換わる古い行）はたどらない。削除された契約は経路に含めない。
    """
    if not start_ids:
        return False
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH RECURSIVE reach(id) AS (
                SELECT c.id
                FROM contract_management.contracts c
                WHERE c.id = ANY(%s) AND c.is_deleted = false
              UNION
                SELECT d.depends_on_contract_id
                FROM reach r
                JOIN contract_management.contract_dependencies d ON d.contract_id = r.id
                JOIN contract_management.contracts t ON t.id = d.depends_on_contract_id
                WHERE r.id <> %s AND t.is_deleted = false
            )
            SELECT 1 FROM reach WHERE id = %s LIMIT 1
            """,
            (start_ids, skip_source_id, target_id),
        )
        return cur.fetchone() is not None


def is_payment_target(conn: PgConnection, contract_id: int) -> bool:
    """他の契約（削除されていないもの）が、この契約を支払方法にしているか。"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM contract_management.contracts
            WHERE payment_contract_id = %s AND is_deleted = false
            LIMIT 1
            """,
            (contract_id,),
        )
        return cur.fetchone() is not None


def _columns(data: ContractData, category_id: int) -> dict[str, object]:
    return {
        "name": data.name,
        "has_contract": data.has_contract,
        "category_id": category_id,
        "status": data.status,
        "homepage": data.homepage,
        "memo": data.memo,
        "login_password": data.login_password,
        "login_passkey": data.login_passkey,
        "login_2fa_mail": data.login_2fa_mail,
        "login_2fa_tel": data.login_2fa_tel,
        "twofa_mail_address": data.twofa_mail_address,
        "twofa_tel_number": data.twofa_tel_number,
        "username": data.username,
        "registered_email": data.registered_email,
        "fee_amount": data.fee_amount,
        "fee_cycle": data.fee_cycle,
        "renewal_date": data.renewal_date,
        "contract_date": data.contract_date,
        "contract_date_precision": data.contract_date_precision,
        "trial_end_date": data.trial_end_date,
        "end_date": data.end_date,
        "auto_renewal": data.auto_renewal,
        "holder_name": data.holder_name,
        "member_number": data.member_number,
        "cancel_notice_days": data.cancel_notice_days,
        "cancellation_fee": data.cancellation_fee,
        "min_term_months": data.min_term_months,
        "contact_phone": data.contact_phone,
        "contact_email": data.contact_email,
        "contact_hours": data.contact_hours,
        "cancellation_method": data.cancellation_method,
        "payment_contract_id": data.payment_contract_id,
    }


def insert_contract(conn: PgConnection, user_id: int, category_id: int, data: ContractData) -> int:
    cols = _columns(data, category_id)
    # パスワードは、指定があるときだけ入れる（API キーでは常に未設定）
    if data.password is not None:
        cols["password"] = data.password
    cols["user_id"] = user_id
    keys = ", ".join(cols)
    marks = ", ".join(["%s"] * len(cols))
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO contract_management.contracts ({keys}) VALUES ({marks}) RETURNING id",
            tuple(cols.values()),
        )
        return int(cur.fetchone()["id"])


def update_contract(conn: PgConnection, contract_id: int, category_id: int, data: ContractData) -> None:
    """全項目を置き換える。パスワードは、指定があるときだけ変える（無いときは保存済みの値のまま）。"""
    cols = _columns(data, category_id)
    if data.password is not None:
        cols["password"] = data.password
    sets = ", ".join(f"{k} = %s" for k in cols)
    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE contract_management.contracts SET {sets} WHERE id = %s",
            (*cols.values(), contract_id),
        )


def replace_dependencies(conn: PgConnection, contract_id: int, depends_on_ids: tuple[int, ...]) -> None:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM contract_management.contract_dependencies WHERE contract_id = %s", (contract_id,))
        for dep in depends_on_ids:
            cur.execute(
                "INSERT INTO contract_management.contract_dependencies (contract_id, depends_on_contract_id) "
                "VALUES (%s, %s)",
                (contract_id, dep),
            )


def soft_delete_contract(conn: PgConnection, contract_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE contract_management.contracts SET is_deleted = true WHERE id = %s",
            (contract_id,),
        )


def remove_from_plan(conn: PgConnection, user_id: int, contract_id: int) -> bool:
    """解約順から外し、残りの `position` を 1 からの連番に付け直す。外れたら True。"""
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM contract_management.cancellation_plan WHERE user_id = %s AND contract_id = %s",
            (user_id, contract_id),
        )
        removed = cur.rowcount > 0
        if removed:
            cur.execute(
                """
                UPDATE contract_management.cancellation_plan p
                SET position = r.n
                FROM (
                    SELECT contract_id, ROW_NUMBER() OVER (ORDER BY position) AS n
                    FROM contract_management.cancellation_plan
                    WHERE user_id = %s
                ) r
                WHERE p.user_id = %s AND p.contract_id = r.contract_id
                """,
                (user_id, user_id),
            )
        return removed
