from __future__ import annotations

from decimal import Decimal

from app.errors import InvalidInputError, NotFoundError
from app.logger import write
from app.repos import (
    get_budget_item,
    get_budget_period,
    list_budget_items,
    sum_expenses_by_budget_item_for_payment_month,
    sum_expenses_by_budget_item_for_usage_range,
)


def _fmt(value: Decimal) -> str:
    return f"{value:.2f}"


def usage_date_report(user_id: int, budget_period_id: int) -> dict[str, object]:
    write("INF", f"利用日基準集計要求 user_id={user_id} budget_period_id={budget_period_id}")
    period = get_budget_period(user_id, budget_period_id)
    if period is None:
        write("WRN", f"利用日基準集計失敗 user_id={user_id} budget_period_id={budget_period_id} 理由=対象なし")
        raise NotFoundError()
    sums = sum_expenses_by_budget_item_for_usage_range(user_id, period.start_date, period.end_date)
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


def payment_month_report(user_id: int, year_month: str) -> dict[str, object]:
    write("INF", f"支払発生月基準集計要求 user_id={user_id} year_month={year_month}")
    parts = year_month.split("-")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        raise InvalidInputError("年月不正")
    year, month = int(parts[0]), int(parts[1])
    if not (1 <= month <= 12):
        raise InvalidInputError("年月不正")
    sums = sum_expenses_by_budget_item_for_payment_month(user_id, year, month)
    items: list[dict[str, object]] = []
    for budget_item_id, total in sums.items():
        if total <= 0:
            continue
        budget_item = get_budget_item(user_id, budget_item_id)
        name = budget_item.name if budget_item is not None else ""
        items.append({"budget_item_id": budget_item_id, "name": name, "actual_amount": _fmt(total)})
    items.sort(key=lambda entry: entry["budget_item_id"])
    write("INF", f"支払発生月基準集計成功 user_id={user_id} year_month={year_month} count={len(items)}")
    return {"items": items}
