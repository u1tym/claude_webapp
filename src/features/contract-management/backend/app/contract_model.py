"""契約の入力の検査と正規化（api-design.md「契約の入力（登録・更新）」）。DB には触れない。

DB を見ないと決められない検査（区分・依存契約・支払方法が本人の削除されていない契約・区分か、
金融機関の区分か、循環しないか）は、サービス層で行う。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from pydantic import BaseModel, ConfigDict, StrictBool, StrictInt, StrictStr

from app.common import optional_text, required_text
from app.errors import InvalidInputError

NAME_MAX = 200
STATUSES = ("active", "paused", "cancelled")
FEE_CYCLES = ("yearly", "monthly")
LOGIN_METHODS = ("password", "passkey", "2fa_mail", "2fa_tel")
DATE_PRECISIONS = ("day", "month", "year", "unknown")

_DATE_RE = {
    "day": re.compile(r"^(\d{4})-(\d{2})-(\d{2})$"),
    "month": re.compile(r"^(\d{4})-(\d{2})$"),
    "year": re.compile(r"^(\d{4})$"),
}

# 契約を伴う契約だけの項目（契約を伴わない契約には指定できない）
CONTRACT_ONLY_FIELDS = (
    "fee_amount",
    "fee_cycle",
    "renewal_date",
    "contract_date",
    "contract_date_precision",
    "trial_end_date",
    "end_date",
    "auto_renewal",
    "holder_name",
    "member_number",
    "cancel_notice_days",
    "cancellation_fee",
    "min_term_months",
    "contact_phone",
    "contact_email",
    "contact_hours",
    "cancellation_method",
    "depends_on_ids",
    "payment_contract_id",
)


class ContractIn(BaseModel):
    """要求の本文。型は厳密に検査する（"1" を整数として受け付けない）。"""

    model_config = ConfigDict(extra="forbid")

    name: StrictStr
    has_contract: StrictBool = True
    category_id: StrictInt | None = None
    status: StrictStr = "active"
    homepage: StrictStr | None = None
    memo: StrictStr | None = None
    login_methods: list[StrictStr] = []
    twofa_mail_address: StrictStr | None = None
    twofa_tel_number: StrictStr | None = None
    username: StrictStr | None = None
    password: StrictStr | None = None
    registered_email: StrictStr | None = None
    fee_amount: StrictInt | None = None
    fee_cycle: StrictStr | None = None
    renewal_date: StrictStr | None = None
    contract_date: StrictStr | None = None
    contract_date_precision: StrictStr | None = None
    trial_end_date: StrictStr | None = None
    end_date: StrictStr | None = None
    auto_renewal: StrictBool | None = None
    holder_name: StrictStr | None = None
    member_number: StrictStr | None = None
    cancel_notice_days: StrictInt | None = None
    cancellation_fee: StrictStr | None = None
    min_term_months: StrictInt | None = None
    contact_phone: StrictStr | None = None
    contact_email: StrictStr | None = None
    contact_hours: StrictStr | None = None
    cancellation_method: StrictStr | None = None
    depends_on_ids: list[StrictInt] = []
    payment_contract_id: StrictInt | None = None


@dataclass(frozen=True)
class ContractData:
    """検査・正規化した入力。DB の列に対応する。"""

    name: str
    has_contract: bool
    category_id: int | None
    status: str
    homepage: str | None
    memo: str | None
    login_password: bool
    login_passkey: bool
    login_2fa_mail: bool
    login_2fa_tel: bool
    twofa_mail_address: str | None
    twofa_tel_number: str | None
    username: str | None
    registered_email: str | None
    fee_amount: int | None
    fee_cycle: str | None
    renewal_date: date | None
    contract_date: date | None
    contract_date_precision: str | None
    trial_end_date: date | None
    end_date: date | None
    auto_renewal: bool | None
    holder_name: str | None
    member_number: str | None
    cancel_notice_days: int | None
    cancellation_fee: str | None
    min_term_months: int | None
    contact_phone: str | None
    contact_email: str | None
    contact_hours: str | None
    cancellation_method: str | None
    depends_on_ids: tuple[int, ...]
    payment_contract_id: int | None
    # パスワードの値。None は「指定なし」（更新では保存済みの値を変えない）
    password: str | None = None
    # 本文に password が含まれていたか
    password_given: bool = False


def parse_iso_date(value: str, what: str) -> date:
    """`YYYY-MM-DD` だけを受け付ける（`20261101` などは不可）。"""
    m = _DATE_RE["day"].match(value.strip())
    if m is None:
        raise InvalidInputError(f"{what}の形式が不正")
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError as exc:
        raise InvalidInputError(f"{what}が存在しない日付") from exc


def parse_contract_date(value: str, precision: str) -> date:
    """精度に応じた形式の文字列を、日付にする。使わない月・日は 1 で埋める。"""
    m = _DATE_RE[precision].match(value.strip())
    if m is None:
        raise InvalidInputError("契約日の形式が精度と合わない")
    parts = [int(g) for g in m.groups()]
    year = parts[0]
    month = parts[1] if len(parts) > 1 else 1
    day = parts[2] if len(parts) > 2 else 1
    try:
        return date(year, month, day)
    except ValueError as exc:
        raise InvalidInputError("契約日が存在しない日付") from exc


def format_contract_date(value: date | None, precision: str | None) -> str | None:
    """保存した日付と精度から、応答の形式の文字列にする。"""
    if value is None or precision is None or precision == "unknown":
        return None
    if precision == "day":
        return value.strftime("%Y-%m-%d")
    if precision == "month":
        return value.strftime("%Y-%m")
    if precision == "year":
        return value.strftime("%Y")
    return None


def _check_choice(value: str | None, choices: tuple[str, ...], what: str) -> None:
    if value is not None and value not in choices:
        raise InvalidInputError(f"{what}が不正")


def _non_negative(value: int | None, what: str) -> int | None:
    if value is not None and value < 0:
        raise InvalidInputError(f"{what}が負")
    return value


def validate_contract(body: ContractIn, *, allow_password: bool) -> ContractData:
    """入力を検査して正規化する。違反は InvalidInputError（400）。

    allow_password が False（API キー）のとき、本文に password が含まれていたら、値によらず入力不正にする。
    """
    given = body.model_fields_set

    password_given = "password" in given
    if password_given and not allow_password:
        raise InvalidInputError("API キーではパスワードを指定できない")
    password: str | None = None
    if body.password is not None:
        if body.password == "":
            raise InvalidInputError("パスワードが空")
        password = body.password

    name = required_text(body.name, NAME_MAX)
    _check_choice(body.status, STATUSES, "ステータス")

    methods = body.login_methods
    for method in methods:
        _check_choice(method, LOGIN_METHODS, "ログイン方法")
    if len(set(methods)) != len(methods):
        raise InvalidInputError("ログイン方法が重複")

    twofa_mail = optional_text(body.twofa_mail_address)
    twofa_tel = optional_text(body.twofa_tel_number)
    if twofa_mail is not None and "2fa_mail" not in methods:
        raise InvalidInputError("2段階認証（メール）を選んでいないのに送付先がある")
    if twofa_tel is not None and "2fa_tel" not in methods:
        raise InvalidInputError("2段階認証（TEL）を選んでいないのに送付先がある")

    holder = optional_text(body.holder_name)
    member = optional_text(body.member_number)
    cancel_fee = optional_text(body.cancellation_fee)
    phone = optional_text(body.contact_phone)
    contact_email = optional_text(body.contact_email)
    hours = optional_text(body.contact_hours)
    method_text = optional_text(body.cancellation_method)

    # 維持費（金額と周期はどちらも指定するか、どちらも指定しない）
    _check_choice(body.fee_cycle, FEE_CYCLES, "維持費の周期")
    if (body.fee_amount is None) != (body.fee_cycle is None):
        raise InvalidInputError("維持費の金額と周期は、どちらも指定する")
    fee_amount = _non_negative(body.fee_amount, "維持費")
    cancel_notice_days = _non_negative(body.cancel_notice_days, "解約の受付期限")
    min_term_months = _non_negative(body.min_term_months, "最低契約期間")

    renewal = parse_iso_date(body.renewal_date, "更新日") if body.renewal_date is not None else None
    trial_end = parse_iso_date(body.trial_end_date, "無料期間の終了日") if body.trial_end_date is not None else None
    end_date = parse_iso_date(body.end_date, "契約終了日") if body.end_date is not None else None

    # 契約日と精度
    _check_choice(body.contract_date_precision, DATE_PRECISIONS, "契約日の精度")
    precision = body.contract_date_precision
    contract_date: date | None = None
    if precision in ("day", "month", "year"):
        if body.contract_date is None:
            raise InvalidInputError("契約日が必要")
        contract_date = parse_contract_date(body.contract_date, precision)
    elif body.contract_date is not None:
        raise InvalidInputError("精度が不明または無いのに契約日がある")

    if body.end_date is not None and not (body.has_contract and body.status == "cancelled"):
        raise InvalidInputError("契約終了日はステータスが解約のときだけ")

    ids = body.depends_on_ids
    if len(set(ids)) != len(ids):
        raise InvalidInputError("依存契約が重複")
    if any(i <= 0 for i in ids):
        raise InvalidInputError("依存契約の ID が不正")
    if body.payment_contract_id is not None and body.payment_contract_id <= 0:
        raise InvalidInputError("支払方法の ID が不正")

    if not body.has_contract:
        # 契約を伴わない契約は、契約を伴う契約だけの項目を持たない（指定されたら入力不正）
        present = [
            name_
            for name_, value in (
                ("fee_amount", fee_amount),
                ("fee_cycle", body.fee_cycle),
                ("renewal_date", renewal),
                ("contract_date", body.contract_date),
                ("contract_date_precision", precision),
                ("trial_end_date", trial_end),
                ("end_date", end_date),
                ("auto_renewal", body.auto_renewal),
                ("holder_name", holder),
                ("member_number", member),
                ("cancel_notice_days", cancel_notice_days),
                ("cancellation_fee", cancel_fee),
                ("min_term_months", min_term_months),
                ("contact_phone", phone),
                ("contact_email", contact_email),
                ("contact_hours", hours),
                ("cancellation_method", method_text),
                ("depends_on_ids", ids or None),
                ("payment_contract_id", body.payment_contract_id),
            )
            if value is not None
        ]
        if present:
            raise InvalidInputError(f"契約を伴わないのに契約の項目がある {','.join(present)}")

    return ContractData(
        name=name,
        has_contract=body.has_contract,
        category_id=body.category_id,
        status=body.status,
        homepage=optional_text(body.homepage),
        memo=optional_text(body.memo),
        login_password="password" in methods,
        login_passkey="passkey" in methods,
        login_2fa_mail="2fa_mail" in methods,
        login_2fa_tel="2fa_tel" in methods,
        twofa_mail_address=twofa_mail,
        twofa_tel_number=twofa_tel,
        username=optional_text(body.username),
        registered_email=optional_text(body.registered_email),
        fee_amount=fee_amount,
        fee_cycle=body.fee_cycle,
        renewal_date=renewal,
        contract_date=contract_date,
        contract_date_precision=precision,
        trial_end_date=trial_end,
        end_date=end_date,
        auto_renewal=body.auto_renewal,
        holder_name=holder,
        member_number=member,
        cancel_notice_days=cancel_notice_days,
        cancellation_fee=cancel_fee,
        min_term_months=min_term_months,
        contact_phone=phone,
        contact_email=contact_email,
        contact_hours=hours,
        cancellation_method=method_text,
        depends_on_ids=tuple(ids),
        payment_contract_id=body.payment_contract_id,
        password=password,
        password_given=password_given,
    )
