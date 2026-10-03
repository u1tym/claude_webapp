"""契約の表現（api-design.md「契約の表現（Contract）」）の組み立て。

どの表現にも、パスワードの値を含めない。含めるのは、設定されているか（has_password）と、
「パスワード未設定」か（password_unset）だけである。
"""

from __future__ import annotations

from psycopg2.extensions import connection as PgConnection

from app.contract_model import format_contract_date

CONTRACT_COLUMNS = """
    id, user_id, category_id, name, has_contract, status, homepage, memo,
    login_password, login_passkey, login_2fa_mail, login_2fa_tel,
    twofa_mail_address, twofa_tel_number, username,
    (password IS NOT NULL) AS has_password, registered_email,
    fee_amount, fee_cycle, renewal_date, contract_date, contract_date_precision,
    trial_end_date, end_date, auto_renewal, holder_name, member_number,
    cancel_notice_days, cancellation_fee, min_term_months,
    contact_phone, contact_email, contact_hours, cancellation_method,
    payment_contract_id
"""
# password の値そのものは、取得する列に含めない（has_password だけ）。


def _iso(value: object) -> str | None:
    return None if value is None else value.isoformat()  # type: ignore[attr-defined]


def _login_methods(row: dict[str, object]) -> list[str]:
    methods: list[str] = []
    if row["login_password"]:
        methods.append("password")
    if row["login_passkey"]:
        methods.append("passkey")
    if row["login_2fa_mail"]:
        methods.append("2fa_mail")
    if row["login_2fa_tel"]:
        methods.append("2fa_tel")
    return methods


def _names(conn: PgConnection, sql: str, ids: list[int]) -> dict[int, list[dict[str, object]]]:
    """(契約 ID, 関連する契約 ID, 名称) の行を、契約 ID ごとの [{id, name}] にまとめる（関連の ID 昇順）。"""
    result: dict[int, list[dict[str, object]]] = {i: [] for i in ids}
    if not ids:
        return result
    with conn.cursor() as cur:
        cur.execute(sql, (ids,))
        for r in cur.fetchall():
            result[int(r["owner_id"])].append({"id": int(r["rel_id"]), "name": str(r["rel_name"])})
    return result


def build_views(conn: PgConnection, rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """`CONTRACT_COLUMNS` で取得した行から、契約の表現のリストを作る（行の順を保つ）。

    関連（区分、依存契約、支払方法、依存されている契約、支払方法にしている契約）は、行数によらず、
    決まった回数の問い合わせでまとめて取得する。削除された契約は、関連に含めない。
    """
    if not rows:
        return []
    ids = [int(r["id"]) for r in rows]  # type: ignore[arg-type]
    category_ids = sorted({int(r["category_id"]) for r in rows})  # type: ignore[arg-type]

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, name, is_financial FROM contract_management.categories WHERE id = ANY(%s)",
            (category_ids,),
        )
        categories = {
            int(c["id"]): {"id": int(c["id"]), "name": str(c["name"]), "is_financial": bool(c["is_financial"])}
            for c in cur.fetchall()
        }

    depends_on = _names(
        conn,
        """
        SELECT d.contract_id AS owner_id, t.id AS rel_id, t.name AS rel_name
        FROM contract_management.contract_dependencies d
        JOIN contract_management.contracts t ON t.id = d.depends_on_contract_id
        WHERE d.contract_id = ANY(%s) AND t.is_deleted = false
        ORDER BY d.contract_id, t.id
        """,
        ids,
    )
    depended_by = _names(
        conn,
        """
        SELECT d.depends_on_contract_id AS owner_id, s.id AS rel_id, s.name AS rel_name
        FROM contract_management.contract_dependencies d
        JOIN contract_management.contracts s ON s.id = d.contract_id
        WHERE d.depends_on_contract_id = ANY(%s) AND s.is_deleted = false
        ORDER BY d.depends_on_contract_id, s.id
        """,
        ids,
    )
    payment_for = _names(
        conn,
        """
        SELECT c.payment_contract_id AS owner_id, c.id AS rel_id, c.name AS rel_name
        FROM contract_management.contracts c
        WHERE c.payment_contract_id = ANY(%s) AND c.is_deleted = false
        ORDER BY c.payment_contract_id, c.id
        """,
        ids,
    )
    payment_ids = sorted({int(r["payment_contract_id"]) for r in rows if r["payment_contract_id"] is not None})  # type: ignore[arg-type]
    payment_contracts: dict[int, dict[str, object]] = {}
    if payment_ids:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name FROM contract_management.contracts WHERE id = ANY(%s) AND is_deleted = false",
                (payment_ids,),
            )
            payment_contracts = {int(p["id"]): {"id": int(p["id"]), "name": str(p["name"])} for p in cur.fetchall()}

    views: list[dict[str, object]] = []
    for r in rows:
        cid = int(r["id"])  # type: ignore[arg-type]
        has_password = bool(r["has_password"])
        payment_id = r["payment_contract_id"]
        views.append(
            {
                "id": cid,
                "name": str(r["name"]),
                "has_contract": bool(r["has_contract"]),
                "category": categories[int(r["category_id"])],  # type: ignore[arg-type]
                "status": str(r["status"]),
                "homepage": r["homepage"],
                "memo": r["memo"],
                "login_methods": _login_methods(r),
                "twofa_mail_address": r["twofa_mail_address"],
                "twofa_tel_number": r["twofa_tel_number"],
                "username": r["username"],
                "has_password": has_password,
                "password_unset": bool(r["login_password"]) and not has_password,
                "registered_email": r["registered_email"],
                "fee_amount": r["fee_amount"],
                "fee_cycle": r["fee_cycle"],
                "renewal_date": _iso(r["renewal_date"]),
                "contract_date": format_contract_date(
                    r["contract_date"], r["contract_date_precision"]  # type: ignore[arg-type]
                ),
                "contract_date_precision": r["contract_date_precision"],
                "trial_end_date": _iso(r["trial_end_date"]),
                "end_date": _iso(r["end_date"]),
                "auto_renewal": r["auto_renewal"],
                "holder_name": r["holder_name"],
                "member_number": r["member_number"],
                "cancel_notice_days": r["cancel_notice_days"],
                "cancellation_fee": r["cancellation_fee"],
                "min_term_months": r["min_term_months"],
                "contact_phone": r["contact_phone"],
                "contact_email": r["contact_email"],
                "contact_hours": r["contact_hours"],
                "cancellation_method": r["cancellation_method"],
                "depends_on": depends_on[cid],
                "payment_contract": (
                    payment_contracts.get(int(payment_id)) if payment_id is not None else None  # type: ignore[arg-type]
                ),
                "depended_by": depended_by[cid],
                "payment_for": payment_for[cid],
            }
        )
    return views


def fetch_views(conn: PgConnection, user_id: int, contract_ids: list[int]) -> list[dict[str, object]]:
    """本人の削除されていない契約を、指定した ID の順に、表現にして返す（無い ID は飛ばす）。"""
    if not contract_ids:
        return []
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {CONTRACT_COLUMNS}
            FROM contract_management.contracts
            WHERE user_id = %s AND is_deleted = false AND id = ANY(%s)
            """,
            (user_id, contract_ids),
        )
        by_id = {int(r["id"]): dict(r) for r in cur.fetchall()}
    rows = [by_id[i] for i in contract_ids if i in by_id]
    return build_views(conn, rows)
