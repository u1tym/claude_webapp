from __future__ import annotations

from decimal import Decimal

from app.errors import InvalidInputError, NotFoundError
from app.logger import write
from app.repos import (
    get_budget_period,
    list_budget_items,
    sum_expenses_by_budget_item_for_usage_range,
    sum_expenses_by_payment_date,
)


def _fmt(value: Decimal) -> str:
    return f"{value:.2f}"


def usage_date_report(user_id: int, budget_period_id: int, include_credit: bool = False) -> dict[str, object]:
    write(
        "INF",
        f"利用日基準集計要求 user_id={user_id} budget_period_id={budget_period_id} include_credit={include_credit}",
    )
    period = get_budget_period(user_id, budget_period_id)
    if period is None:
        write("WRN", f"利用日基準集計失敗 user_id={user_id} budget_period_id={budget_period_id} 理由=対象なし")
        raise NotFoundError()
    sums = sum_expenses_by_budget_item_for_usage_range(
        user_id, period.start_date, period.end_date, include_credit
    )
    items: list[dict[str, object]] = []
    for budget_item in list_budget_items(user_id, budget_period_id):
        actual = sums.get(budget_item.id, Decimal("0"))
        items.append(
            {
                "budget_item_id": budget_item.id,
                "name": budget_item.name,
                "budget_amount": _fmt(budget_item.amount),
                "actual_amount": _fmt(actual),
                "difference": _fmt(budget_item.amount - actual),
            }
        )
    write("INF", f"利用日基準集計成功 user_id={user_id} budget_period_id={budget_period_id} count={len(items)}")
    return {
        "budget_period": {
            "id": period.id,
            "title": period.title,
            "start_date": period.start_date.isoformat(),
            "end_date": period.end_date.isoformat(),
        },
        "items": items,
    }


def payment_date_report(user_id: int, year_month: str) -> dict[str, object]:
    write("INF", f"支払日毎集計要求 user_id={user_id} year_month={year_month}")
    parts = year_month.split("-")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        raise InvalidInputError("年月不正")
    year, month = int(parts[0]), int(parts[1])
    if not (1 <= month <= 12):
        raise InvalidInputError("年月不正")
    sums = sum_expenses_by_payment_date(user_id, year, month)
    items: list[dict[str, object]] = []
    for payment_date in sorted(sums.keys()):
        bucket = sums[payment_date]
        items.append(
            {
                "payment_date": payment_date.isoformat(),
                "normal_amount": _fmt(bucket["normal"]),
                "credit_amount": _fmt(bucket["credit"]),
                "credit_payment_amount": _fmt(bucket["credit_payment"]),
            }
        )
    write("INF", f"支払日毎集計成功 user_id={user_id} year_month={year_month} count={len(items)}")
    return {"items": items}
