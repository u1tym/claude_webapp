"""DDL の制約・インデックスのテスト（db-design.md）。制約が DB で効くことを、直接の SQL で確認する。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import psycopg2.errors as pg
import pytest

from app.db import get_conn
from conftest import Owner, execute, insert_category, insert_contract


def violates(error: type[Exception], sql: str, params: tuple[object, ...] = ()) -> None:
    """SQL が、指定した種類の制約違反で失敗することを確認する（失敗したらロールバックされる）。"""
    with pytest.raises(error):
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)


@pytest.fixture()
def owner(make_owner: Callable[..., Owner]) -> Owner:
    return make_owner()


@pytest.fixture()
def cat(owner: Owner) -> int:
    return insert_category(owner, "区分")


def _c(owner: Owner, cat: int, **cols: Any) -> int:
    return insert_contract(owner, cat, "契約", **cols)


def _bad_contract(owner: Owner, cat: int, error: type[Exception] = pg.CheckViolation, **cols: Any) -> None:
    keys = ["user_id", "category_id", "name", *cols]
    params = (owner.id, cat, "契約", *cols.values())
    violates(
        error,
        f"INSERT INTO contract_management.contracts ({', '.join(keys)}) VALUES ({', '.join(['%s'] * len(keys))})",
        params,
    )


# ---- categories ----


def test_schema_and_tables_exist() -> None:
    rows = execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'contract_management' ORDER BY 1"
    )
    assert [r["table_name"] for r in rows] == ["cancellation_plan", "categories", "contract_dependencies", "contracts"]


def test_category_rules(owner: Owner, make_owner: Callable[..., Owner]) -> None:
    insert_category(owner, "重複")
    violates(
        pg.UniqueViolation,
        "INSERT INTO contract_management.categories (user_id, name) VALUES (%s, '重複')",
        (owner.id,),
    )
    # 削除済み同士・削除済みと同名の未削除は入る
    execute("UPDATE contract_management.categories SET is_deleted = true WHERE user_id = %s AND name = '重複'", (owner.id,))
    insert_category(owner, "重複")
    execute(
        "INSERT INTO contract_management.categories (user_id, name, is_deleted) VALUES (%s, '重複', true)",
        (owner.id,),
    )
    # 他ユーザなら同名も入る
    insert_category(make_owner(), "重複")
    violates(pg.CheckViolation, "INSERT INTO contract_management.categories (user_id, name) VALUES (%s, '')", (owner.id,))
    violates(
        pg.ForeignKeyViolation,
        "INSERT INTO contract_management.categories (user_id, name) VALUES (-1, 'x')",
    )


def test_default_category_rules(owner: Owner) -> None:
    execute("INSERT INTO contract_management.categories (user_id, name, is_default) VALUES (%s, 'その他', true)", (owner.id,))
    # 利用者ごとに「その他」は 1 つ
    violates(
        pg.UniqueViolation,
        "INSERT INTO contract_management.categories (user_id, name, is_default) VALUES (%s, 'その他2', true)",
        (owner.id,),
    )
    # 「その他」は金融機関・削除済みにならない
    violates(
        pg.CheckViolation,
        "UPDATE contract_management.categories SET is_financial = true WHERE user_id = %s AND is_default",
        (owner.id,),
    )
    violates(
        pg.CheckViolation,
        "UPDATE contract_management.categories SET is_deleted = true WHERE user_id = %s AND is_default",
        (owner.id,),
    )


# ---- contracts ----


def test_contract_defaults(owner: Owner, cat: int) -> None:
    row = execute("SELECT * FROM contract_management.contracts WHERE id = %s", (_c(owner, cat),))[0]
    assert row["has_contract"] is True and row["status"] == "active" and row["is_deleted"] is False
    assert row["password"] is None and row["auto_renewal"] is None
    assert (row["login_password"], row["login_passkey"], row["login_2fa_mail"], row["login_2fa_tel"]) == (False,) * 4


def test_contract_basic_checks(owner: Owner, cat: int) -> None:
    violates(pg.CheckViolation, "INSERT INTO contract_management.contracts (user_id, category_id, name) VALUES (%s, %s, '')", (owner.id, cat))
    _bad_contract(owner, cat, status="終了")
    _bad_contract(owner, cat, password="")
    _bad_contract(owner, cat, fee_amount=-1, fee_cycle="monthly")
    _bad_contract(owner, cat, cancel_notice_days=-1)
    _bad_contract(owner, cat, min_term_months=-1)
    _c(owner, cat, password="   ")  # 空白だけ・複数行は可
    _c(owner, cat, fee_amount=0, fee_cycle="yearly", cancel_notice_days=0, min_term_months=0)


def test_fee_pair_and_cycle(owner: Owner, cat: int) -> None:
    _bad_contract(owner, cat, fee_amount=100)
    _bad_contract(owner, cat, fee_cycle="monthly")
    _bad_contract(owner, cat, fee_amount=100, fee_cycle="weekly")


def test_contract_date_and_precision(owner: Owner, cat: int) -> None:
    _bad_contract(owner, cat, contract_date_precision="always")
    _bad_contract(owner, cat, contract_date="2020-04-01")  # 精度がない
    _bad_contract(owner, cat, contract_date="2020-04-01", contract_date_precision="unknown")
    _bad_contract(owner, cat, contract_date_precision="day")  # 日付がない
    _bad_contract(owner, cat, contract_date_precision="month")
    _c(owner, cat, contract_date="2020-04-01", contract_date_precision="month")
    _c(owner, cat, contract_date_precision="unknown")


def test_end_date_only_for_cancelled_contract(owner: Owner, cat: int) -> None:
    _bad_contract(owner, cat, end_date="2026-09-30")  # 有効
    _bad_contract(owner, cat, status="paused", end_date="2026-09-30")
    _bad_contract(owner, cat, has_contract=False, status="cancelled", end_date="2026-09-30")
    _c(owner, cat, status="cancelled", end_date="2026-09-30")


@pytest.mark.parametrize(
    "col,value",
    [
        ("fee_amount", 1),
        ("renewal_date", "2026-01-01"),
        ("trial_end_date", "2026-01-01"),
        ("auto_renewal", False),
        ("holder_name", "x"),
        ("member_number", "x"),
        ("cancel_notice_days", 1),
        ("cancellation_fee", "x"),
        ("min_term_months", 1),
        ("contact_phone", "x"),
        ("contact_email", "x"),
        ("contact_hours", "x"),
        ("cancellation_method", "x"),
    ],
)
def test_no_contract_items_must_be_null(owner: Owner, cat: int, col: str, value: object) -> None:
    _bad_contract(owner, cat, has_contract=False, **{col: value})
    _c(owner, cat, has_contract=True, **{col: value} if not col.startswith("fee") else {"fee_amount": 1, "fee_cycle": "monthly"})


def test_no_contract_rejects_dates_fee_cycle_and_payment(owner: Owner, cat: int) -> None:
    _bad_contract(owner, cat, has_contract=False, fee_amount=1, fee_cycle="monthly")
    _bad_contract(owner, cat, has_contract=False, contract_date="2020-01-01", contract_date_precision="year")
    _bad_contract(owner, cat, has_contract=False, contract_date_precision="unknown")
    target = _c(owner, cat)
    _bad_contract(owner, cat, has_contract=False, payment_contract_id=target)
    # 契約を伴わなくても、ユーザ名・パスワード・メモ・ログイン方法・ステータスは持てる
    _c(owner, cat, has_contract=False, status="paused", username="u", password="p", memo="m", login_password=True)


def test_twofa_destination_requires_method(owner: Owner, cat: int) -> None:
    _bad_contract(owner, cat, twofa_mail_address="a@b.c")
    _bad_contract(owner, cat, twofa_tel_number="090")
    _bad_contract(owner, cat, login_2fa_tel=True, twofa_mail_address="a@b.c")
    _c(owner, cat, login_2fa_mail=True, twofa_mail_address="a@b.c")
    _c(owner, cat, login_2fa_tel=True, twofa_tel_number="090")


def test_payment_contract_rules(owner: Owner, cat: int) -> None:
    target = _c(owner, cat)
    user = _c(owner, cat, payment_contract_id=target)
    violates(pg.CheckViolation, "UPDATE contract_management.contracts SET payment_contract_id = id WHERE id = %s", (user,))
    violates(pg.ForeignKeyViolation, "UPDATE contract_management.contracts SET payment_contract_id = -1 WHERE id = %s", (user,))
    violates(pg.ForeignKeyViolation, "DELETE FROM contract_management.contracts WHERE id = %s", (target,))  # 参照されている


def test_contract_foreign_keys(owner: Owner, cat: int) -> None:
    _bad_contract(owner, -1, error=pg.ForeignKeyViolation)
    violates(
        pg.ForeignKeyViolation,
        "INSERT INTO contract_management.contracts (user_id, category_id, name) VALUES (-1, %s, 'x')",
        (cat,),
    )
    # 契約が参照している区分は、物理削除できない
    _c(owner, cat)
    violates(pg.ForeignKeyViolation, "DELETE FROM contract_management.categories WHERE id = %s", (cat,))


def test_imported_entry_is_unique(owner: Owner, cat: int) -> None:
    _c(owner, cat, imported_from_entry_id=123456)
    violates(
        pg.UniqueViolation,
        "INSERT INTO contract_management.contracts (user_id, category_id, name, imported_from_entry_id) VALUES (%s, %s, 'x', 123456)",
        (owner.id, cat),
    )
    _c(owner, cat)  # NULL は重複してよい
    _c(owner, cat)


# ---- contract_dependencies ----


def test_dependency_rules(owner: Owner, cat: int) -> None:
    a, b = _c(owner, cat), _c(owner, cat)
    execute("INSERT INTO contract_management.contract_dependencies VALUES (%s, %s)", (a, b))
    violates(pg.UniqueViolation, "INSERT INTO contract_management.contract_dependencies VALUES (%s, %s)", (a, b))
    violates(pg.CheckViolation, "INSERT INTO contract_management.contract_dependencies VALUES (%s, %s)", (a, a))
    violates(pg.ForeignKeyViolation, "INSERT INTO contract_management.contract_dependencies VALUES (%s, -1)", (a,))
    violates(pg.ForeignKeyViolation, "DELETE FROM contract_management.contracts WHERE id = %s", (b,))
    execute("INSERT INTO contract_management.contract_dependencies VALUES (%s, %s)", (b, a))  # 逆向きは別の行（循環の検査はアプリ側）


# ---- cancellation_plan ----


def _plan(owner: Owner, contract_id: int, position: int) -> None:
    execute(
        "INSERT INTO contract_management.cancellation_plan (user_id, contract_id, position) VALUES (%s, %s, %s)",
        (owner.id, contract_id, position),
    )


def test_cancellation_plan_rules(owner: Owner, cat: int, make_owner: Callable[..., Owner]) -> None:
    a, b = _c(owner, cat), _c(owner, cat)
    _plan(owner, a, 1)
    violates(
        pg.CheckViolation,
        "INSERT INTO contract_management.cancellation_plan (user_id, contract_id, position) VALUES (%s, %s, 0)",
        (owner.id, b),
    )
    violates(  # 同じ契約は 1 回だけ
        pg.UniqueViolation,
        "INSERT INTO contract_management.cancellation_plan (user_id, contract_id, position) VALUES (%s, %s, 2)",
        (owner.id, a),
    )
    # 同じ順位は、トランザクションの終わり（commit）で拒否される
    with pytest.raises(pg.UniqueViolation):
        _plan(owner, b, 1)
    # 他ユーザなら、同じ順位も入る
    other = make_owner()
    other_cat = insert_category(other, "他")
    _plan(other, _c(other, other_cat), 1)
    violates(pg.ForeignKeyViolation, "DELETE FROM contract_management.contracts WHERE id = %s", (a,))


def test_cancellation_plan_positions_can_be_swapped_in_one_transaction(owner: Owner, cat: int) -> None:
    a, b = _c(owner, cat), _c(owner, cat)
    _plan(owner, a, 1)
    _plan(owner, b, 2)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE contract_management.cancellation_plan SET position = 2 WHERE contract_id = %s", (a,))
            cur.execute("UPDATE contract_management.cancellation_plan SET position = 1 WHERE contract_id = %s", (b,))
    rows = execute(
        "SELECT contract_id FROM contract_management.cancellation_plan WHERE user_id = %s ORDER BY position", (owner.id,)
    )
    assert [r["contract_id"] for r in rows] == [b, a]


# ---- インデックス ----


def test_indexes_exist() -> None:
    rows = execute("SELECT indexname FROM pg_indexes WHERE schemaname = 'contract_management'")
    names = {r["indexname"] for r in rows}
    assert {
        "ux_categories_user_name",
        "ux_categories_user_default",
        "ix_contracts_user",
        "ix_contracts_user_category",
        "ux_contracts_imported_entry",
        "ix_contracts_payment_contract",
        "ix_contract_dependencies_target",
        "ux_cancellation_plan_position",
    } <= names


def test_ddl_can_be_applied_twice() -> None:
    from pathlib import Path

    sql = (Path(__file__).resolve().parent.parent / "backend" / "sql" / "01_contract_management.sql").read_text(encoding="utf-8")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(sql)
