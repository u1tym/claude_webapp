"""契約の表現（Contract）の組み立てのテスト（api-design.md「契約の表現（Contract）」）。"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from app.contract_view import fetch_views
from app.db import get_conn
from conftest import Owner, execute, insert_category, insert_contract


_category = insert_category
_contract = insert_contract


def _views(owner: Owner, ids: list[int]) -> list[dict[str, Any]]:
    with get_conn() as conn:
        return fetch_views(conn, owner.id, ids)  # type: ignore[return-value]


def test_full_representation(make_owner: Callable[..., Owner]) -> None:
    owner = make_owner()
    video = _category(owner, "動画配信")
    bank = _category(owner, "銀行", True)
    card = _contract(owner, bank, "Aカード", has_contract=False)
    provider = _contract(owner, video, "プロバイダ")
    cid = _contract(
        owner,
        video,
        "ネット動画",
        status="active",
        homepage="https://e.com",
        login_password=True,
        login_2fa_mail=True,
        twofa_mail_address="me@e.com",
        username="taro",
        password="secret",
        registered_email="me@e.com",
        fee_amount=990,
        fee_cycle="monthly",
        renewal_date="2026-11-05",
        contract_date="2020-04-01",
        contract_date_precision="month",
        auto_renewal=True,
        holder_name="山田",
        member_number="A-1",
        cancel_notice_days=7,
        cancellation_fee="なし",
        min_term_months=12,
        contact_phone="0120",
        contact_email="s@e.com",
        contact_hours="平日",
        cancellation_method="マイページ",
        payment_contract_id=card,
    )
    execute(
        "INSERT INTO contract_management.contract_dependencies (contract_id, depends_on_contract_id) VALUES (%s, %s)",
        (cid, provider),
    )
    [v] = _views(owner, [cid])
    assert v["id"] == cid and v["name"] == "ネット動画" and v["has_contract"] is True
    assert v["category"] == {"id": video, "name": "動画配信", "is_financial": False}
    assert v["status"] == "active" and v["homepage"] == "https://e.com" and v["memo"] is None
    assert v["login_methods"] == ["password", "2fa_mail"]
    assert v["twofa_mail_address"] == "me@e.com" and v["twofa_tel_number"] is None
    assert v["username"] == "taro" and v["registered_email"] == "me@e.com"
    assert v["has_password"] is True and v["password_unset"] is False
    assert (v["fee_amount"], v["fee_cycle"]) == (990, "monthly")
    assert v["renewal_date"] == "2026-11-05" and v["trial_end_date"] is None and v["end_date"] is None
    assert v["contract_date"] == "2020-04" and v["contract_date_precision"] == "month"
    assert v["auto_renewal"] is True and v["holder_name"] == "山田" and v["member_number"] == "A-1"
    assert (v["cancel_notice_days"], v["min_term_months"]) == (7, 12)
    assert v["cancellation_fee"] == "なし" and v["cancellation_method"] == "マイページ"
    assert (v["contact_phone"], v["contact_email"], v["contact_hours"]) == ("0120", "s@e.com", "平日")
    assert v["depends_on"] == [{"id": provider, "name": "プロバイダ"}]
    assert v["payment_contract"] == {"id": card, "name": "Aカード"}
    assert v["depended_by"] == [] and v["payment_for"] == []
    # パスワードの値は、どこにも現れない
    assert "secret" not in json.dumps(v, ensure_ascii=False)
    assert "password" not in v
    # 逆引き
    [p] = _views(owner, [provider])
    assert p["depended_by"] == [{"id": cid, "name": "ネット動画"}] and p["depends_on"] == []
    [c] = _views(owner, [card])
    assert c["payment_for"] == [{"id": cid, "name": "ネット動画"}]
    assert c["has_contract"] is False and c["category"]["is_financial"] is True


def test_contract_date_formats(make_owner: Callable[..., Owner]) -> None:
    owner = make_owner()
    cat = _category(owner, "x")
    day = _contract(owner, cat, "d", contract_date="2020-04-03", contract_date_precision="day")
    month = _contract(owner, cat, "m", contract_date="2020-04-01", contract_date_precision="month")
    year = _contract(owner, cat, "y", contract_date="2020-01-01", contract_date_precision="year")
    unknown = _contract(owner, cat, "u", contract_date_precision="unknown")
    none = _contract(owner, cat, "n")
    got = {v["name"]: (v["contract_date"], v["contract_date_precision"]) for v in _views(owner, [day, month, year, unknown, none])}
    assert got == {
        "d": ("2020-04-03", "day"),
        "m": ("2020-04", "month"),
        "y": ("2020", "year"),
        "u": (None, "unknown"),
        "n": (None, None),
    }


def test_password_flags(make_owner: Callable[..., Owner]) -> None:
    owner = make_owner()
    cat = _category(owner, "x")
    set_ = _contract(owner, cat, "set", login_password=True, password="p")
    unset = _contract(owner, cat, "unset", login_password=True)
    not_pw = _contract(owner, cat, "other", login_passkey=True)
    pw_without_method = _contract(owner, cat, "nomethod", password="p")
    got = {v["name"]: (v["has_password"], v["password_unset"]) for v in _views(owner, [set_, unset, not_pw, pw_without_method])}
    assert got == {
        "set": (True, False),
        "unset": (False, True),  # ユーザ名とパスワードを使い、パスワードが未設定
        "other": (False, False),  # ユーザ名とパスワードを使わないので「未設定」ではない
        "nomethod": (True, False),
    }


def test_no_contract_items_are_null_or_empty(make_owner: Callable[..., Owner]) -> None:
    owner = make_owner()
    cat = _category(owner, "x")
    cid = _contract(owner, cat, "アカウント", has_contract=False, login_password=True, username="u", password="p")
    [v] = _views(owner, [cid])
    for key in (
        "fee_amount", "fee_cycle", "renewal_date", "contract_date", "contract_date_precision",
        "trial_end_date", "end_date", "auto_renewal", "holder_name", "member_number",
        "cancel_notice_days", "cancellation_fee", "min_term_months", "contact_phone",
        "contact_email", "contact_hours", "cancellation_method", "payment_contract",
    ):
        assert v[key] is None, key
    assert v["depends_on"] == [] and v["depended_by"] == [] and v["payment_for"] == []
    assert v["status"] == "active" and v["has_contract"] is False


def test_deleted_related_contracts_are_excluded(make_owner: Callable[..., Owner]) -> None:
    owner = make_owner()
    cat = _category(owner, "x")
    bank = _category(owner, "銀行", True)
    card = _contract(owner, bank, "カード")
    dep = _contract(owner, cat, "依存先")
    main = _contract(owner, cat, "本体", payment_contract_id=card)
    other = _contract(owner, cat, "依存元", payment_contract_id=card)
    for a, b in ((main, dep), (other, main)):
        execute(
            "INSERT INTO contract_management.contract_dependencies (contract_id, depends_on_contract_id) VALUES (%s, %s)",
            (a, b),
        )
    [v] = _views(owner, [main])
    assert [d["name"] for d in v["depends_on"]] == ["依存先"] and [d["name"] for d in v["depended_by"]] == ["依存元"]
    assert v["payment_contract"]["name"] == "カード"
    for cid in (dep, other, card):
        execute("UPDATE contract_management.contracts SET is_deleted = true WHERE id = %s", (cid,))
    [v] = _views(owner, [main])
    assert v["depends_on"] == [] and v["depended_by"] == [] and v["payment_contract"] is None
    # 削除済みの契約自体は、取得されない
    assert _views(owner, [dep]) == []


def test_order_follows_ids_and_other_users_are_excluded(make_owner: Callable[..., Owner]) -> None:
    a = make_owner()
    b = make_owner()
    ca = _category(a, "x")
    cb = _category(b, "x")
    first = _contract(a, ca, "1")
    second = _contract(a, ca, "2")
    foreign = _contract(b, cb, "他人")
    assert [v["name"] for v in _views(a, [second, first])] == ["2", "1"]
    assert [v["id"] for v in _views(a, [first, foreign, 999999999, second])] == [first, second]
    assert _views(a, []) == []


def test_many_contracts_use_constant_queries(make_owner: Callable[..., Owner]) -> None:
    owner = make_owner()
    cat = _category(owner, "x")
    ids = [_contract(owner, cat, f"c{i}") for i in range(30)]
    for i in range(1, 30):
        execute(
            "INSERT INTO contract_management.contract_dependencies (contract_id, depends_on_contract_id) VALUES (%s, %s)",
            (ids[i], ids[i - 1]),
        )
    counted: list[str] = []

    class SpyCursor:
        def __init__(self, cur: Any) -> None:
            self._cur = cur

        def __enter__(self) -> "SpyCursor":
            self._cur.__enter__()
            return self

        def __exit__(self, *a: Any) -> Any:
            return self._cur.__exit__(*a)

        def execute(self, sql: str, params: Any = None) -> None:
            counted.append(sql)
            self._cur.execute(sql, params)

        def __getattr__(self, name: str) -> Any:
            return getattr(self._cur, name)

    class SpyConn:
        def __init__(self, conn: Any) -> None:
            self._conn = conn

        def cursor(self, *a: Any, **k: Any) -> SpyCursor:
            return SpyCursor(self._conn.cursor(*a, **k))

    with get_conn() as conn:
        views = fetch_views(SpyConn(conn), owner.id, ids)  # type: ignore[arg-type]
    assert len(views) == 30
    assert views[5]["depends_on"] == [{"id": ids[4], "name": "c4"}]
    assert views[5]["depended_by"] == [{"id": ids[6], "name": "c6"}]
    assert len(counted) <= 6  # 件数によらず、決まった回数
