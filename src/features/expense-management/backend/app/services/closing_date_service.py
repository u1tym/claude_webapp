from __future__ import annotations

from datetime import date, timedelta

import jpholiday

_WEEKDAY_KIND = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        next_month_first = date(year + 1, 1, 1)
    else:
        next_month_first = date(year, month + 1, 1)
    return (next_month_first - date(year, month, 1)).days


def add_months(year: int, month: int, offset: int) -> tuple[int, int]:
    total = (year * 12 + (month - 1)) + offset
    return total // 12, (total % 12) + 1


def compute_actual_date(
    year: int,
    month: int,
    base_day: int,
    exclusion_kinds: frozenset[str],
    shift_direction: str | None,
) -> date:
    """Resolve a day-of-month basis value to a concrete date for (year, month).

    `base_day` may exceed the number of days in the month (e.g. 31 in
    February); in that case it is first clamped to the month's last day.
    While the candidate date matches a registered exclusion (a specific
    weekday, or the fact that `base_day` did not exist in the month), it is
    shifted one day at a time in `shift_direction` until no exclusion
    matches.
    """
    days_in_month = _days_in_month(year, month)
    clamped_day = min(base_day, days_in_month)
    candidate = date(year, month, clamped_day)
    day_was_nonexistent = base_day > days_in_month
    step = timedelta(days=-1) if shift_direction == "earlier" else timedelta(days=1)

    while True:
        matches = (
            (day_was_nonexistent and "nonexistent_day" in exclusion_kinds)
            or (_WEEKDAY_KIND[candidate.weekday()] in exclusion_kinds)
            or ("holiday" in exclusion_kinds and jpholiday.is_holiday(candidate))
        )
        if not matches:
            return candidate
        candidate = candidate + step
        day_was_nonexistent = False


def estimate_payment_date(
    usage_date: date,
    closing_day: int,
    closing_day_shift_direction: str | None,
    closing_day_exclusions: frozenset[str],
    payment_month_offset: int,
    payment_day: int,
    payment_day_shift_direction: str | None,
    payment_day_exclusions: frozenset[str],
) -> date:
    if closing_day == 0:
        return usage_date

    actual_closing_date = compute_actual_date(
        usage_date.year, usage_date.month, closing_day, closing_day_exclusions, closing_day_shift_direction
    )
    payment_year, payment_month = add_months(
        actual_closing_date.year, actual_closing_date.month, payment_month_offset
    )
    return compute_actual_date(
        payment_year, payment_month, payment_day, payment_day_exclusions, payment_day_shift_direction
    )
