from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from app.errors import InvalidInputError, NotFoundError
from app.logger import write
from app.repos import (
    BudgetItemRow,
    BudgetPeriodRow,
    get_budget_item,
    get_budget_period,
    insert_budget_item,
    insert_budget_period,
    list_budget_items,
    list_budget_periods,
    logical_delete_budget_item,
    update_budget_item,
    update_budget_period,
)


def format_amount(value: Decimal) -> str:
    return f"{value:.2f}"


def parse_amount(value: str) -> Decimal:
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise InvalidInputError("金額不正") from exc
    if amount < 0:
        raise InvalidInputError("金額が負")
    return amount


def _period_body(row: BudgetPeriodRow) -> dict[str, object]:
    return {
        "id": row.id,
        "title": row.title,
        "start_date": row.start_date.isoformat(),
        "end_date": row.end_date.isoformat(),
    }


def _validate_title(title: str) -> str:
    trimmed = title.strip()
    if trimmed == "":
        raise InvalidInputError("タイトルが空")
    return trimmed


def _item_body(row: BudgetItemRow) -> dict[str, object]:
    return {
        "id": row.id,
        "budget_period_id": row.budget_period_id,
        "name": row.name,
        "amount": format_amount(row.amount),
        "display_order": row.display_order,
        "memo": row.memo,
    }


def _normalize_memo(memo: str | None) -> str | None:
    if memo is None:
        return None
    trimmed = memo.strip()
    return trimmed or None


def _validate_period_range(start_date: date, end_date: date) -> None:
    if end_date < start_date:
        raise InvalidInputError("終了日が開始日より前")


def list_periods(user_id: int) -> list[dict[str, object]]:
    write("INF", f"予算期間一覧要求 user_id={user_id}")
    items = [_period_body(row) for row in list_budget_periods(user_id)]
    write("INF", f"予算期間一覧成功 user_id={user_id} count={len(items)}")
    return items


def create_period(user_id: int, title: str, start_date: date, end_date: date) -> dict[str, object]:
    write("INF", f"予算期間作成要求 user_id={user_id} title={title} start_date={start_date} end_date={end_date}")
    trimmed_title = _validate_title(title)
    _validate_period_range(start_date, end_date)
    row = insert_budget_period(user_id, trimmed_title, start_date, end_date)
    write("INF", f"予算期間作成成功 user_id={user_id} budget_period_id={row.id}")
    return _period_body(row)


def change_period(
    user_id: int, budget_period_id: int, title: str, start_date: date, end_date: date
) -> dict[str, object]:
    write(
        "INF",
        f"予算期間更新要求 user_id={user_id} budget_period_id={budget_period_id} title={title} "
        f"start_date={start_date} end_date={end_date}",
    )
    existing = get_budget_period(user_id, budget_period_id)
    if existing is None:
        write("WRN", f"予算期間更新失敗 user_id={user_id} budget_period_id={budget_period_id} 理由=対象なし")
        raise NotFoundError()
    trimmed_title = _validate_title(title)
    _validate_period_range(start_date, end_date)
    update_budget_period(budget_period_id, user_id, trimmed_title, start_date, end_date)
    updated = get_budget_period(user_id, budget_period_id)
    assert updated is not None
    write("INF", f"予算期間更新成功 user_id={user_id} budget_period_id={budget_period_id}")
    return _period_body(updated)


def duplicate_period(
    user_id: int, source_budget_period_id: int, title: str, start_date: date, end_date: date
) -> dict[str, object]:
    write(
        "INF",
        f"予算期間複製要求 user_id={user_id} source={source_budget_period_id} title={title} "
        f"start_date={start_date} end_date={end_date}",
    )
    source = get_budget_period(user_id, source_budget_period_id)
    if source is None:
        write("WRN", f"予算期間複製失敗 user_id={user_id} 理由=複製元なし")
        raise NotFoundError()
    trimmed_title = _validate_title(title)
    _validate_period_range(start_date, end_date)
    new_period = insert_budget_period(user_id, trimmed_title, start_date, end_date)
    copied_items: list[dict[str, object]] = []
    for source_item in list_budget_items(user_id, source.id):
        # memo is deliberately not copied (REQ-002 only duplicates name/amount/display_order).
        new_item = insert_budget_item(
            user_id, new_period.id, source_item.name, source_item.amount, source_item.display_order, None
        )
        copied_items.append(_item_body(new_item))
    write(
        "INF",
        f"予算期間複製成功 user_id={user_id} budget_period_id={new_period.id} "
        f"items={len(copied_items)}",
    )
    body = _period_body(new_period)
    body["budget_items"] = copied_items
    return body


def require_own_period(user_id: int, budget_period_id: int) -> BudgetPeriodRow:
    period = get_budget_period(user_id, budget_period_id)
    if period is None:
        raise NotFoundError()
    return period


def list_items(user_id: int, budget_period_id: int) -> list[dict[str, object]]:
    write("INF", f"予算項目一覧要求 user_id={user_id} budget_period_id={budget_period_id}")
    require_own_period(user_id, budget_period_id)
    items = [_item_body(row) for row in list_budget_items(user_id, budget_period_id)]
    write("INF", f"予算項目一覧成功 user_id={user_id} budget_period_id={budget_period_id} count={len(items)}")
    return items


def _validate_item_input(name: str, amount_raw: str, display_order: int) -> tuple[str, Decimal]:
    trimmed = name.strip()
    if trimmed == "":
        raise InvalidInputError("項目名が空")
    amount = parse_amount(amount_raw)
    return trimmed, amount


def add_item(
    user_id: int,
    budget_period_id: int,
    name: str,
    amount_raw: str,
    display_order: int,
    memo: str | None = None,
) -> dict[str, object]:
    write(
        "INF",
        f"予算項目追加要求 user_id={user_id} budget_period_id={budget_period_id} name={name}",
    )
    require_own_period(user_id, budget_period_id)
    trimmed, amount = _validate_item_input(name, amount_raw, display_order)
    row = insert_budget_item(user_id, budget_period_id, trimmed, amount, display_order, _normalize_memo(memo))
    write("INF", f"予算項目追加成功 user_id={user_id} budget_item_id={row.id}")
    return _item_body(row)


def change_item(
    user_id: int,
    budget_item_id: int,
    name: str,
    amount_raw: str,
    display_order: int,
    memo: str | None = None,
) -> dict[str, object]:
    write("INF", f"予算項目更新要求 user_id={user_id} budget_item_id={budget_item_id}")
    existing = get_budget_item(user_id, budget_item_id)
    if existing is None or existing.is_deleted:
        write("WRN", f"予算項目更新失敗 user_id={user_id} budget_item_id={budget_item_id} 理由=対象なし")
        raise NotFoundError()
    trimmed, amount = _validate_item_input(name, amount_raw, display_order)
    update_budget_item(budget_item_id, user_id, trimmed, amount, display_order, _normalize_memo(memo))
    updated = get_budget_item(user_id, budget_item_id)
    assert updated is not None
    write("INF", f"予算項目更新成功 user_id={user_id} budget_item_id={budget_item_id}")
    return _item_body(updated)


def remove_item(user_id: int, budget_item_id: int) -> None:
    write("INF", f"予算項目削除要求 user_id={user_id} budget_item_id={budget_item_id}")
    existing = get_budget_item(user_id, budget_item_id)
    if existing is None or existing.is_deleted:
        write("WRN", f"予算項目削除失敗 user_id={user_id} budget_item_id={budget_item_id} 理由=対象なし")
        raise NotFoundError()
    logical_delete_budget_item(budget_item_id, user_id)
    write("INF", f"予算項目削除成功 user_id={user_id} budget_item_id={budget_item_id}")
