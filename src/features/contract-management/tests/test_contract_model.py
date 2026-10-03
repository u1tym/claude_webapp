"""契約の入力の検査と正規化の単体テスト（DB を使わない）。api-design.md「契約の入力（登録・更新）」。"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from app.contract_model import (
    ContractData,
    ContractIn,
    format_contract_date,
    parse_contract_date,
    validate_contract,
)
from app.errors import InvalidInputError


def ok(allow_password: bool = True, **fields: Any) -> ContractData:
    fields.setdefault("name", "契約")
    return validate_contract(ContractIn(**fields), allow_password=allow_password)


def bad(allow_password: bool = True, **fields: Any) -> None:
    fields.setdefault("name", "契約")
    with pytest.raises(InvalidInputError):
        validate_contract(ContractIn(**fields), allow_password=allow_password)


def test_name_only_defaults() -> None:
    d = ok(name="  名称  ")
    assert d.name == "名称" and d.has_contract is True and d.status == "active"
    assert d.category_id is None and d.password is None and d.password_given is False
    assert d.depends_on_ids == () and not any(
        (d.login_password, d.login_passkey, d.login_2fa_mail, d.login_2fa_tel)
    )


@pytest.mark.parametrize("name", ["", "   ", "あ" * 201])
def test_name_invalid(name: str) -> None:
    bad(name=name)


def test_name_boundary() -> None:
    assert ok(name="あ" * 200).name == "あ" * 200


def test_types_are_strict() -> None:
    for fields in (
        {"fee_amount": "100", "fee_cycle": "monthly"},
        {"has_contract": "true"},
        {"category_id": "1"},
        {"cancel_notice_days": 1.5},
        {"fee_amount": True, "fee_cycle": "monthly"},
        {"unknown_field": 1},
    ):
        with pytest.raises(ValidationError):
            ContractIn(name="x", **fields)


def test_status_choices() -> None:
    for s in ("active", "paused"):
        assert ok(status=s).status == s
    assert ok(status="cancelled").status == "cancelled"
    bad(status="終了")


def test_text_fields_are_trimmed_and_blank_becomes_none() -> None:
    d = ok(homepage=" https://e.com ", memo="  ", username=" u ", registered_email="")
    assert (d.homepage, d.memo, d.username, d.registered_email) == ("https://e.com", None, "u", None)


def test_login_methods() -> None:
    d = ok(login_methods=["password", "2fa_tel"])
    assert (d.login_password, d.login_passkey, d.login_2fa_mail, d.login_2fa_tel) == (True, False, False, True)
    bad(login_methods=["password", "password"])
    bad(login_methods=["sms"])


def test_twofa_destination_requires_method() -> None:
    d = ok(login_methods=["2fa_mail", "2fa_tel"], twofa_mail_address=" a@b.c ", twofa_tel_number="090")
    assert (d.twofa_mail_address, d.twofa_tel_number) == ("a@b.c", "090")
    bad(login_methods=["2fa_tel"], twofa_mail_address="a@b.c")
    bad(login_methods=["2fa_mail"], twofa_tel_number="090")
    bad(twofa_mail_address="a@b.c")
    # 送付先は未入力でもよい
    assert ok(login_methods=["2fa_mail"]).twofa_mail_address is None
    # 空白だけの送付先は未入力として扱う（方式がなくても可）
    assert ok(twofa_mail_address="  ").twofa_mail_address is None


def test_password_rules() -> None:
    assert ok(password="  a\nb  ").password == "  a\nb  "  # 空白・複数行はそのまま
    assert ok(password="   ").password == "   "
    assert ok(password="x").password_given is True
    bad(password="")
    # API キー（allow_password=False）では、指定そのものが入力不正（null でも）
    bad(allow_password=False, password="x")
    bad(allow_password=False, password=None)
    assert ok(allow_password=False).password_given is False


def test_fee() -> None:
    d = ok(fee_amount=0, fee_cycle="yearly")
    assert (d.fee_amount, d.fee_cycle) == (0, "yearly")
    bad(fee_amount=100)
    bad(fee_cycle="monthly")
    bad(fee_amount=-1, fee_cycle="monthly")
    bad(fee_amount=1, fee_cycle="weekly")
    assert ok().fee_amount is None


def test_non_negative_numbers() -> None:
    d = ok(cancel_notice_days=0, min_term_months=0)
    assert (d.cancel_notice_days, d.min_term_months) == (0, 0)
    bad(cancel_notice_days=-1)
    bad(min_term_months=-1)


def test_dates() -> None:
    d = ok(renewal_date="2026-11-05", trial_end_date="2026-10-31")
    assert d.renewal_date == date(2026, 11, 5) and d.trial_end_date == date(2026, 10, 31)
    for v in ("20261105", "2026-11", "2026/11/05", "2026-02-30", "2026-13-01", "", "x"):
        bad(renewal_date=v)


def test_contract_date_precision() -> None:
    assert ok(contract_date="2020-04-03", contract_date_precision="day").contract_date == date(2020, 4, 3)
    assert ok(contract_date="2020-04", contract_date_precision="month").contract_date == date(2020, 4, 1)
    assert ok(contract_date="2020", contract_date_precision="year").contract_date == date(2020, 1, 1)
    u = ok(contract_date_precision="unknown")
    assert u.contract_date is None and u.contract_date_precision == "unknown"
    assert ok().contract_date_precision is None
    # 精度に合わない・欠けている・不要な契約日
    bad(contract_date="2020-04", contract_date_precision="day")
    bad(contract_date="2020-04-03", contract_date_precision="month")
    bad(contract_date="2020-04-03", contract_date_precision="year")
    bad(contract_date_precision="day")
    bad(contract_date="2020", contract_date_precision="unknown")
    bad(contract_date="2020")
    bad(contract_date="2020-02-30", contract_date_precision="day")
    bad(contract_date="2020-13", contract_date_precision="month")
    bad(contract_date_precision="always")


def test_format_contract_date_roundtrip() -> None:
    assert format_contract_date(date(2020, 4, 3), "day") == "2020-04-03"
    assert format_contract_date(date(2020, 4, 1), "month") == "2020-04"
    assert format_contract_date(date(2020, 1, 1), "year") == "2020"
    assert format_contract_date(None, "unknown") is None
    assert format_contract_date(None, None) is None
    assert format_contract_date(date(2020, 1, 1), "unknown") is None
    assert parse_contract_date("2020-04", "month") == date(2020, 4, 1)


def test_end_date_only_when_cancelled_contract() -> None:
    assert ok(status="cancelled", end_date="2026-09-30").end_date == date(2026, 9, 30)
    assert ok(status="cancelled").end_date is None
    bad(status="active", end_date="2026-09-30")
    bad(status="paused", end_date="2026-09-30")


def test_depends_on_ids_and_payment() -> None:
    d = ok(depends_on_ids=[3, 1, 2], payment_contract_id=9)
    assert d.depends_on_ids == (3, 1, 2) and d.payment_contract_id == 9
    bad(depends_on_ids=[1, 1])
    bad(depends_on_ids=[0])
    bad(depends_on_ids=[-1])
    bad(payment_contract_id=0)


def test_contract_only_fields_rejected_without_contract() -> None:
    # 契約を伴わなくても、名称・区分・ステータス・ログイン関連・メモなどは指定できる
    d = ok(
        has_contract=False,
        category_id=3,
        status="paused",
        homepage="h",
        memo="m",
        login_methods=["password", "2fa_mail"],
        twofa_mail_address="a@b.c",
        username="u",
        password="p",
        registered_email="e@e.e",
    )
    assert d.has_contract is False and d.status == "paused" and d.password == "p"
    cases: list[dict[str, Any]] = [
        {"fee_amount": 1, "fee_cycle": "monthly"},
        {"renewal_date": "2026-11-05"},
        {"contract_date": "2020", "contract_date_precision": "year"},
        {"contract_date_precision": "unknown"},
        {"trial_end_date": "2026-11-05"},
        {"status": "cancelled", "end_date": "2026-09-30"},
        {"auto_renewal": False},
        {"holder_name": "x"},
        {"member_number": "x"},
        {"cancel_notice_days": 0},
        {"cancellation_fee": "x"},
        {"min_term_months": 0},
        {"contact_phone": "x"},
        {"contact_email": "x"},
        {"contact_hours": "x"},
        {"cancellation_method": "x"},
        {"depends_on_ids": [1]},
        {"payment_contract_id": 1},
    ]
    for extra in cases:
        bad(has_contract=False, **extra)
    # 空白だけの文字列は未指定として扱う
    assert ok(has_contract=False, holder_name="  ").holder_name is None
