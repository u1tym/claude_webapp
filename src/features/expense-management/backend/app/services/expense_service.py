from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from app.errors import InvalidInputError, NotFoundError
from app.logger import write
from app.repos import (
    ExpenseRow,
    get_budget_item,
    get_expense,
    get_payment_method,
    insert_expense,
    list_expenses,
    logical_delete_expense,
    update_expense,
)


class ExpenseInput:
    def __init__(
        self,
        usage_date: date,
        budget_item_id: int,
        purpose: str,
        amount: str,
        payment_method_id: int,
        memo: str | None,
        payment_date: date,
    ) -> None:
        self.usage_date = usage_date
        self.budget_item_id = budget_item_id
        self.purpose = purpose
        self.amount = amount
        self.payment_method_id = payment_method_id
        self.memo = memo
        self.payment_date = payment_date


def _parse_amount(value: str) -> Decimal:
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise InvalidInputError("金額不正") from exc
    if amount < 0:
        raise InvalidInputError("金額が負")
    return amount


def _validate(user_id: int, data: ExpenseInput) -> tuple[str, Decimal]:
    trimmed = data.purpose.strip()
    if trimmed == "":
        raise InvalidInputError("用途が空")
    amount = _parse_amount(data.amount)
    budget_item = get_budget_item(user_id, data.budget_item_id)
    if budget_item is None or budget_item.is_deleted:
        raise InvalidInputError("予算区分が不正")
    payment_method = get_payment_method(user_id, data.payment_method_id)
    if payment_method is None or payment_method.is_deleted:
        raise InvalidInputError("支出方法が不正")
    return trimmed, amount


def _body(row: ExpenseRow) -> dict[str, object]:
    return {
        "id": row.id,
        "usage_date": row.usage_date.isoformat(),
        "budget_item_id": row.budget_item_id,
        "purpose": row.purpose,
        "amount": f"{row.amount:.2f}",
        "payment_method_id": row.payment_method_id,
        "memo": row.memo,
        "payment_date": row.payment_date.isoformat(),
        "created_at": row.created_at.isoformat(),
    }


def list_for_range(user_id: int, start_date: date, end_date: date) -> list[dict[str, object]]:
    write("INF", f"支出記録一覧要求 user_id={user_id} start_date={start_date} end_date={end_date}")
    if end_date < start_date:
        raise InvalidInputError("終了日が開始日より前")
    items = [_body(row) for row in list_expenses(user_id, start_date, end_date)]
    write("INF", f"支出記録一覧成功 user_id={user_id} count={len(items)}")
    return items


def create_expense(user_id: int, data: ExpenseInput) -> dict[str, object]:
    write(
        "INF",
        f"支出記録登録要求 user_id={user_id} usage_date={data.usage_date} "
        f"budget_item_id={data.budget_item_id} payment_method_id={data.payment_method_id}",
    )
    trimmed, amount = _validate(user_id, data)
    row = insert_expense(
        user_id,
        data.budget_item_id,
        data.payment_method_id,
        data.usage_date,
        trimmed,
        amount,
        (data.memo.strip() or None) if data.memo is not None else None,
        data.payment_date,
    )
    write("INF", f"支出記録登録成功 user_id={user_id} expense_id={row.id}")
    return _body(row)


def change_expense(user_id: int, expense_id: int, data: ExpenseInput) -> dict[str, object]:
    write("INF", f"支出記録更新要求 user_id={user_id} expense_id={expense_id}")
    existing = get_expense(user_id, expense_id)
    if existing is None or existing.is_deleted:
        write("WRN", f"支出記録更新失敗 user_id={user_id} expense_id={expense_id} 理由=対象なし")
        raise NotFoundError()
    trimmed, amount = _validate(user_id, data)
    update_expense(
        expense_id,
        user_id,
        data.budget_item_id,
        data.payment_method_id,
        data.usage_date,
        trimmed,
        amount,
        (data.memo.strip() or None) if data.memo is not None else None,
        data.payment_date,
    )
    updated = get_expense(user_id, expense_id)
    assert updated is not None
    write("INF", f"支出記録更新成功 user_id={user_id} expense_id={expense_id}")
    return _body(updated)


def remove_expense(user_id: int, expense_id: int) -> None:
    write("INF", f"支出記録削除要求 user_id={user_id} expense_id={expense_id}")
    existing = get_expense(user_id, expense_id)
    if existing is None or existing.is_deleted:
        write("WRN", f"支出記録削除失敗 user_id={user_id} expense_id={expense_id} 理由=対象なし")
        raise NotFoundError()
    logical_delete_expense(expense_id, user_id)
    write("INF", f"支出記録削除成功 user_id={user_id} expense_id={expense_id}")
