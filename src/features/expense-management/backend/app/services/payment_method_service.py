from __future__ import annotations

from app.errors import InvalidInputError, NotFoundError
from app.logger import write
from app.repos import (
    PaymentMethodRow,
    delete_all_exclusions,
    get_payment_method,
    insert_payment_method,
    list_exclusions,
    list_payment_methods,
    logical_delete_payment_method,
    replace_exclusions,
    update_payment_method,
)

VALID_EXCLUSION_KINDS = frozenset(
    {
        "sunday",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "nonexistent_day",
    }
)
VALID_SHIFT_DIRECTIONS = frozenset({"earlier", "later"})


class PaymentMethodInput:
    def __init__(
        self,
        name: str,
        closing_day: int,
        closing_day_shift_direction: str | None,
        closing_day_exclusions: list[str],
        payment_month_offset: int | None,
        payment_day: int | None,
        payment_day_shift_direction: str | None,
        payment_day_exclusions: list[str],
        display_order: int,
    ) -> None:
        self.name = name
        self.closing_day = closing_day
        self.closing_day_shift_direction = closing_day_shift_direction
        self.closing_day_exclusions = closing_day_exclusions
        self.payment_month_offset = payment_month_offset
        self.payment_day = payment_day
        self.payment_day_shift_direction = payment_day_shift_direction
        self.payment_day_exclusions = payment_day_exclusions
        self.display_order = display_order


def _validate_exclusion_kinds(kinds: list[str]) -> list[str]:
    for kind in kinds:
        if kind not in VALID_EXCLUSION_KINDS:
            raise InvalidInputError("除外条件不正")
    # de-duplicate while preserving order
    seen: set[str] = set()
    result: list[str] = []
    for kind in kinds:
        if kind not in seen:
            seen.add(kind)
            result.append(kind)
    return result


def _validate_input(data: PaymentMethodInput) -> None:
    if data.name.strip() == "":
        raise InvalidInputError("名称が空")
    if not (0 <= data.closing_day <= 31):
        raise InvalidInputError("締め日が範囲外")
    if data.closing_day == 0:
        return
    if data.payment_month_offset is None or data.payment_month_offset < 0:
        raise InvalidInputError("支払月オフセット不正")
    if data.payment_day is None or not (1 <= data.payment_day <= 31):
        raise InvalidInputError("支払日が範囲外")
    if data.closing_day_shift_direction not in VALID_SHIFT_DIRECTIONS:
        raise InvalidInputError("締め日用ずらし方向不正")
    if data.payment_day_shift_direction not in VALID_SHIFT_DIRECTIONS:
        raise InvalidInputError("支払日用ずらし方向不正")
    _validate_exclusion_kinds(data.closing_day_exclusions)
    _validate_exclusion_kinds(data.payment_day_exclusions)


def _body(row: PaymentMethodRow) -> dict[str, object]:
    exclusions = list_exclusions(row.id)
    closing = [{"exclusion_kind": kind} for target, kind in exclusions if target == "closing_day"]
    payment = [{"exclusion_kind": kind} for target, kind in exclusions if target == "payment_day"]
    return {
        "id": row.id,
        "name": row.name,
        "closing_day": row.closing_day,
        "closing_day_shift_direction": row.closing_day_shift_direction,
        "closing_day_exclusions": closing,
        "payment_month_offset": row.payment_month_offset,
        "payment_day": row.payment_day,
        "payment_day_shift_direction": row.payment_day_shift_direction,
        "payment_day_exclusions": payment,
        "display_order": row.display_order,
    }


def list_for_user(user_id: int) -> list[dict[str, object]]:
    write("INF", f"支出方法一覧要求 user_id={user_id}")
    items = [_body(row) for row in list_payment_methods(user_id)]
    write("INF", f"支出方法一覧成功 user_id={user_id} count={len(items)}")
    return items


def create_payment_method(user_id: int, data: PaymentMethodInput) -> dict[str, object]:
    write("INF", f"支出方法登録要求 user_id={user_id} name={data.name} closing_day={data.closing_day}")
    _validate_input(data)
    trimmed = data.name.strip()
    if data.closing_day == 0:
        row = insert_payment_method(user_id, trimmed, 0, None, 0, 0, None, data.display_order)
    else:
        row = insert_payment_method(
            user_id,
            trimmed,
            data.closing_day,
            data.closing_day_shift_direction,
            data.payment_month_offset or 0,
            data.payment_day or 0,
            data.payment_day_shift_direction,
            data.display_order,
        )
        closing_kinds = _validate_exclusion_kinds(data.closing_day_exclusions)
        payment_kinds = _validate_exclusion_kinds(data.payment_day_exclusions)
        if closing_kinds:
            replace_exclusions(row.id, "closing_day", closing_kinds)
        if payment_kinds:
            replace_exclusions(row.id, "payment_day", payment_kinds)
    write("INF", f"支出方法登録成功 user_id={user_id} payment_method_id={row.id}")
    return _body(row)


def change_payment_method(user_id: int, payment_method_id: int, data: PaymentMethodInput) -> dict[str, object]:
    write("INF", f"支出方法更新要求 user_id={user_id} payment_method_id={payment_method_id}")
    existing = get_payment_method(user_id, payment_method_id)
    if existing is None or existing.is_deleted:
        write("WRN", f"支出方法更新失敗 user_id={user_id} payment_method_id={payment_method_id} 理由=対象なし")
        raise NotFoundError()
    _validate_input(data)
    trimmed = data.name.strip()
    if data.closing_day == 0:
        update_payment_method(payment_method_id, user_id, trimmed, 0, None, 0, 0, None, data.display_order)
        delete_all_exclusions(payment_method_id)
    else:
        update_payment_method(
            payment_method_id,
            user_id,
            trimmed,
            data.closing_day,
            data.closing_day_shift_direction,
            data.payment_month_offset or 0,
            data.payment_day or 0,
            data.payment_day_shift_direction,
            data.display_order,
        )
        closing_kinds = _validate_exclusion_kinds(data.closing_day_exclusions)
        payment_kinds = _validate_exclusion_kinds(data.payment_day_exclusions)
        replace_exclusions(payment_method_id, "closing_day", closing_kinds)
        replace_exclusions(payment_method_id, "payment_day", payment_kinds)
    updated = get_payment_method(user_id, payment_method_id)
    assert updated is not None
    write("INF", f"支出方法更新成功 user_id={user_id} payment_method_id={payment_method_id}")
    return _body(updated)


def remove_payment_method(user_id: int, payment_method_id: int) -> None:
    write("INF", f"支出方法削除要求 user_id={user_id} payment_method_id={payment_method_id}")
    existing = get_payment_method(user_id, payment_method_id)
    if existing is None or existing.is_deleted:
        write("WRN", f"支出方法削除失敗 user_id={user_id} payment_method_id={payment_method_id} 理由=対象なし")
        raise NotFoundError()
    logical_delete_payment_method(payment_method_id, user_id)
    write("INF", f"支出方法削除成功 user_id={user_id} payment_method_id={payment_method_id}")


def require_own_active(user_id: int, payment_method_id: int) -> PaymentMethodRow:
    row = get_payment_method(user_id, payment_method_id)
    if row is None or row.is_deleted:
        raise NotFoundError()
    return row


def exclusions_for(payment_method_id: int, target: str) -> frozenset[str]:
    return frozenset(kind for t, kind in list_exclusions(payment_method_id) if t == target)
