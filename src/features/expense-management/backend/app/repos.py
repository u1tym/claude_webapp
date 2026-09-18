from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from app.db import get_conn


@dataclass(frozen=True)
class BudgetPeriodRow:
    id: int
    user_id: int
    title: str
    start_date: date
    end_date: date


@dataclass(frozen=True)
class BudgetItemRow:
    id: int
    user_id: int
    budget_period_id: int
    name: str
    amount: Decimal
    display_order: int
    is_deleted: bool


@dataclass(frozen=True)
class PaymentMethodRow:
    id: int
    user_id: int
    name: str
    closing_day: int
    closing_day_shift_direction: str | None
    payment_month_offset: int
    payment_day: int
    payment_day_shift_direction: str | None
    display_order: int
    is_deleted: bool


@dataclass(frozen=True)
class ExpenseRow:
    id: int
    user_id: int
    budget_item_id: int
    payment_method_id: int
    usage_date: date
    purpose: str
    amount: Decimal
    memo: str | None
    created_at: datetime
    payment_date: date
    is_deleted: bool


def list_budget_periods(user_id: int) -> list[BudgetPeriodRow]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, title, start_date, end_date
                FROM expense_management.budget_periods
                WHERE user_id = %s
                ORDER BY start_date DESC, id DESC
                """,
                (user_id,),
            )
            return [_budget_period_from_row(row) for row in cur.fetchall()]


def get_budget_period(user_id: int, budget_period_id: int) -> BudgetPeriodRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, title, start_date, end_date
                FROM expense_management.budget_periods
                WHERE id = %s AND user_id = %s
                """,
                (budget_period_id, user_id),
            )
            row = cur.fetchone()
            return None if row is None else _budget_period_from_row(row)


def insert_budget_period(user_id: int, title: str, start_date: date, end_date: date) -> BudgetPeriodRow:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO expense_management.budget_periods (user_id, title, start_date, end_date)
                VALUES (%s, %s, %s, %s)
                RETURNING id, user_id, title, start_date, end_date
                """,
                (user_id, title, start_date, end_date),
            )
            row = cur.fetchone()
            assert row is not None
            return _budget_period_from_row(row)


def update_budget_period(
    budget_period_id: int,
    user_id: int,
    title: str,
    start_date: date,
    end_date: date,
) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE expense_management.budget_periods
                SET title = %s, start_date = %s, end_date = %s
                WHERE id = %s AND user_id = %s
                """,
                (title, start_date, end_date, budget_period_id, user_id),
            )


def list_budget_items(
    user_id: int, budget_period_id: int, include_deleted: bool = False
) -> list[BudgetItemRow]:
    query = """
        SELECT id, user_id, budget_period_id, name, amount, display_order, is_deleted
        FROM expense_management.budget_items
        WHERE user_id = %s AND budget_period_id = %s
    """
    if not include_deleted:
        query += " AND is_deleted = false"
    query += " ORDER BY display_order ASC, id ASC"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id, budget_period_id))
            return [_budget_item_from_row(row) for row in cur.fetchall()]


def get_budget_item(user_id: int, budget_item_id: int) -> BudgetItemRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, budget_period_id, name, amount, display_order, is_deleted
                FROM expense_management.budget_items
                WHERE id = %s AND user_id = %s
                """,
                (budget_item_id, user_id),
            )
            row = cur.fetchone()
            return None if row is None else _budget_item_from_row(row)


def insert_budget_item(
    user_id: int,
    budget_period_id: int,
    name: str,
    amount: Decimal,
    display_order: int,
) -> BudgetItemRow:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO expense_management.budget_items
                    (user_id, budget_period_id, name, amount, display_order)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, user_id, budget_period_id, name, amount, display_order, is_deleted
                """,
                (user_id, budget_period_id, name, amount, display_order),
            )
            row = cur.fetchone()
            assert row is not None
            return _budget_item_from_row(row)


def update_budget_item(
    budget_item_id: int,
    user_id: int,
    name: str,
    amount: Decimal,
    display_order: int,
) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE expense_management.budget_items
                SET name = %s, amount = %s, display_order = %s
                WHERE id = %s AND user_id = %s
                """,
                (name, amount, display_order, budget_item_id, user_id),
            )


def logical_delete_budget_item(budget_item_id: int, user_id: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE expense_management.budget_items
                SET is_deleted = true
                WHERE id = %s AND user_id = %s
                """,
                (budget_item_id, user_id),
            )


def _budget_period_from_row(row: dict[str, object]) -> BudgetPeriodRow:
    return BudgetPeriodRow(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        title=str(row["title"]),
        start_date=row["start_date"],
        end_date=row["end_date"],
    )


def _budget_item_from_row(row: dict[str, object]) -> BudgetItemRow:
    return BudgetItemRow(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        budget_period_id=int(row["budget_period_id"]),
        name=str(row["name"]),
        amount=Decimal(row["amount"]),
        display_order=int(row["display_order"]),
        is_deleted=bool(row["is_deleted"]),
    )


def list_payment_methods(user_id: int, include_deleted: bool = False) -> list[PaymentMethodRow]:
    query = """
        SELECT id, user_id, name, closing_day, closing_day_shift_direction,
               payment_month_offset, payment_day, payment_day_shift_direction,
               display_order, is_deleted
        FROM expense_management.payment_methods
        WHERE user_id = %s
    """
    if not include_deleted:
        query += " AND is_deleted = false"
    query += " ORDER BY display_order ASC, id ASC"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id,))
            return [_payment_method_from_row(row) for row in cur.fetchall()]


def get_payment_method(user_id: int, payment_method_id: int) -> PaymentMethodRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, name, closing_day, closing_day_shift_direction,
                       payment_month_offset, payment_day, payment_day_shift_direction,
                       display_order, is_deleted
                FROM expense_management.payment_methods
                WHERE id = %s AND user_id = %s
                """,
                (payment_method_id, user_id),
            )
            row = cur.fetchone()
            return None if row is None else _payment_method_from_row(row)


def insert_payment_method(
    user_id: int,
    name: str,
    closing_day: int,
    closing_day_shift_direction: str | None,
    payment_month_offset: int,
    payment_day: int,
    payment_day_shift_direction: str | None,
    display_order: int,
) -> PaymentMethodRow:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO expense_management.payment_methods
                    (user_id, name, closing_day, closing_day_shift_direction,
                     payment_month_offset, payment_day, payment_day_shift_direction, display_order)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, user_id, name, closing_day, closing_day_shift_direction,
                          payment_month_offset, payment_day, payment_day_shift_direction,
                          display_order, is_deleted
                """,
                (
                    user_id,
                    name,
                    closing_day,
                    closing_day_shift_direction,
                    payment_month_offset,
                    payment_day,
                    payment_day_shift_direction,
                    display_order,
                ),
            )
            row = cur.fetchone()
            assert row is not None
            return _payment_method_from_row(row)


def update_payment_method(
    payment_method_id: int,
    user_id: int,
    name: str,
    closing_day: int,
    closing_day_shift_direction: str | None,
    payment_month_offset: int,
    payment_day: int,
    payment_day_shift_direction: str | None,
    display_order: int,
) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE expense_management.payment_methods
                SET name = %s, closing_day = %s, closing_day_shift_direction = %s,
                    payment_month_offset = %s, payment_day = %s,
                    payment_day_shift_direction = %s, display_order = %s
                WHERE id = %s AND user_id = %s
                """,
                (
                    name,
                    closing_day,
                    closing_day_shift_direction,
                    payment_month_offset,
                    payment_day,
                    payment_day_shift_direction,
                    display_order,
                    payment_method_id,
                    user_id,
                ),
            )


def logical_delete_payment_method(payment_method_id: int, user_id: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE expense_management.payment_methods
                SET is_deleted = true
                WHERE id = %s AND user_id = %s
                """,
                (payment_method_id, user_id),
            )


def list_exclusions(payment_method_id: int) -> list[tuple[str, str]]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT target, exclusion_kind
                FROM expense_management.payment_method_exclusions
                WHERE payment_method_id = %s
                ORDER BY target, exclusion_kind
                """,
                (payment_method_id,),
            )
            return [(str(row["target"]), str(row["exclusion_kind"])) for row in cur.fetchall()]


def replace_exclusions(payment_method_id: int, target: str, exclusion_kinds: list[str]) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM expense_management.payment_method_exclusions
                WHERE payment_method_id = %s AND target = %s
                """,
                (payment_method_id, target),
            )
            for kind in exclusion_kinds:
                cur.execute(
                    """
                    INSERT INTO expense_management.payment_method_exclusions
                        (payment_method_id, target, exclusion_kind)
                    VALUES (%s, %s, %s)
                    """,
                    (payment_method_id, target, kind),
                )


def delete_all_exclusions(payment_method_id: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM expense_management.payment_method_exclusions
                WHERE payment_method_id = %s
                """,
                (payment_method_id,),
            )


def _payment_method_from_row(row: dict[str, object]) -> PaymentMethodRow:
    return PaymentMethodRow(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        name=str(row["name"]),
        closing_day=int(row["closing_day"]),
        closing_day_shift_direction=(
            None if row["closing_day_shift_direction"] is None else str(row["closing_day_shift_direction"])
        ),
        payment_month_offset=int(row["payment_month_offset"]),
        payment_day=int(row["payment_day"]),
        payment_day_shift_direction=(
            None if row["payment_day_shift_direction"] is None else str(row["payment_day_shift_direction"])
        ),
        display_order=int(row["display_order"]),
        is_deleted=bool(row["is_deleted"]),
    )


def list_expenses(user_id: int, start_date: date, end_date: date) -> list[ExpenseRow]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, budget_item_id, payment_method_id, usage_date, purpose,
                       amount, memo, created_at, payment_date, is_deleted
                FROM expense_management.expenses
                WHERE user_id = %s AND usage_date BETWEEN %s AND %s AND is_deleted = false
                ORDER BY usage_date DESC, id DESC
                """,
                (user_id, start_date, end_date),
            )
            return [_expense_from_row(row) for row in cur.fetchall()]


def get_expense(user_id: int, expense_id: int) -> ExpenseRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, budget_item_id, payment_method_id, usage_date, purpose,
                       amount, memo, created_at, payment_date, is_deleted
                FROM expense_management.expenses
                WHERE id = %s AND user_id = %s
                """,
                (expense_id, user_id),
            )
            row = cur.fetchone()
            return None if row is None else _expense_from_row(row)


def insert_expense(
    user_id: int,
    budget_item_id: int,
    payment_method_id: int,
    usage_date: date,
    purpose: str,
    amount: Decimal,
    memo: str | None,
    payment_date: date,
) -> ExpenseRow:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO expense_management.expenses
                    (user_id, budget_item_id, payment_method_id, usage_date, purpose, amount, memo, payment_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, user_id, budget_item_id, payment_method_id, usage_date, purpose,
                          amount, memo, created_at, payment_date, is_deleted
                """,
                (user_id, budget_item_id, payment_method_id, usage_date, purpose, amount, memo, payment_date),
            )
            row = cur.fetchone()
            assert row is not None
            return _expense_from_row(row)


def update_expense(
    expense_id: int,
    user_id: int,
    budget_item_id: int,
    payment_method_id: int,
    usage_date: date,
    purpose: str,
    amount: Decimal,
    memo: str | None,
    payment_date: date,
) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE expense_management.expenses
                SET budget_item_id = %s, payment_method_id = %s, usage_date = %s, purpose = %s,
                    amount = %s, memo = %s, payment_date = %s
                WHERE id = %s AND user_id = %s AND is_deleted = false
                """,
                (
                    budget_item_id,
                    payment_method_id,
                    usage_date,
                    purpose,
                    amount,
                    memo,
                    payment_date,
                    expense_id,
                    user_id,
                ),
            )


def logical_delete_expense(expense_id: int, user_id: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE expense_management.expenses
                SET is_deleted = true
                WHERE id = %s AND user_id = %s
                """,
                (expense_id, user_id),
            )


def sum_expenses_by_budget_item_for_usage_range(
    user_id: int, start_date: date, end_date: date
) -> dict[int, Decimal]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT budget_item_id, COALESCE(SUM(amount), 0) AS total
                FROM expense_management.expenses
                WHERE user_id = %s AND usage_date BETWEEN %s AND %s AND is_deleted = false
                GROUP BY budget_item_id
                """,
                (user_id, start_date, end_date),
            )
            return {int(row["budget_item_id"]): Decimal(row["total"]) for row in cur.fetchall()}


def sum_expenses_by_budget_item_for_payment_month(
    user_id: int, year: int, month: int
) -> dict[int, Decimal]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT budget_item_id, COALESCE(SUM(amount), 0) AS total
                FROM expense_management.expenses
                WHERE user_id = %s
                  AND is_deleted = false
                  AND EXTRACT(YEAR FROM payment_date) = %s
                  AND EXTRACT(MONTH FROM payment_date) = %s
                GROUP BY budget_item_id
                """,
                (user_id, year, month),
            )
            return {int(row["budget_item_id"]): Decimal(row["total"]) for row in cur.fetchall()}


def _expense_from_row(row: dict[str, object]) -> ExpenseRow:
    return ExpenseRow(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        budget_item_id=int(row["budget_item_id"]),
        payment_method_id=int(row["payment_method_id"]),
        usage_date=row["usage_date"],
        purpose=str(row["purpose"]),
        amount=Decimal(row["amount"]),
        memo=(None if row["memo"] is None else str(row["memo"])),
        created_at=row["created_at"],
        payment_date=row["payment_date"],
        is_deleted=bool(row["is_deleted"]),
    )
