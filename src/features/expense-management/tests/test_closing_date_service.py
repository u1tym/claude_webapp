from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.services.closing_date_service import (  # noqa: E402
    add_months,
    compute_actual_date,
    estimate_payment_date,
)


def test_add_months_wraps_year() -> None:
    assert add_months(2026, 11, 2) == (2027, 1)
    assert add_months(2026, 1, -1) == (2025, 12)
    assert add_months(2026, 3, 0) == (2026, 3)


def test_compute_actual_date_no_exclusion_returns_base_day() -> None:
    assert compute_actual_date(2026, 9, 15, frozenset(), None) == date(2026, 9, 15)


def test_compute_actual_date_nonexistent_day_clamped_without_exclusion() -> None:
    # 31 does not exist in February; without the exclusion registered it still
    # must resolve to a concrete date, so it clamps to the month's last day.
    assert compute_actual_date(2026, 2, 31, frozenset(), "earlier") == date(2026, 2, 28)


def test_compute_actual_date_nonexistent_day_with_exclusion_shifts_earlier() -> None:
    # 31 does not exist in February; the clamped candidate (Feb 28) matches the
    # registered "nonexistent_day" exclusion once, so it shifts one more day
    # earlier to Feb 27, which matches no further exclusion.
    result = compute_actual_date(2026, 2, 31, frozenset({"nonexistent_day"}), "earlier")
    assert result == date(2026, 2, 27)


def test_compute_actual_date_weekday_exclusion_shifts_forward() -> None:
    # 2026-09-19 is a Saturday.
    result = compute_actual_date(2026, 9, 19, frozenset({"saturday", "sunday"}), "later")
    assert result == date(2026, 9, 21)
    assert result.weekday() == 0  # Monday


def test_compute_actual_date_weekday_exclusion_shifts_earlier() -> None:
    result = compute_actual_date(2026, 9, 19, frozenset({"saturday", "sunday"}), "earlier")
    assert result == date(2026, 9, 18)
    assert result.weekday() == 4  # Friday


def test_compute_actual_date_holiday_exclusion_shifts_earlier() -> None:
    # 2026-08-11 is Mountain Day (山の日), a fixed-date Japanese national holiday.
    result = compute_actual_date(2026, 8, 11, frozenset({"holiday"}), "earlier")
    assert result == date(2026, 8, 10)


def test_compute_actual_date_holiday_not_excluded_without_kind() -> None:
    # Without "holiday" registered, a national holiday is not shifted.
    assert compute_actual_date(2026, 8, 11, frozenset(), "earlier") == date(2026, 8, 11)


def test_estimate_payment_date_immediate_when_closing_day_zero() -> None:
    result = estimate_payment_date(
        usage_date=date(2026, 9, 5),
        closing_day=0,
        closing_day_shift_direction=None,
        closing_day_exclusions=frozenset(),
        payment_month_offset=0,
        payment_day=0,
        payment_day_shift_direction=None,
        payment_day_exclusions=frozenset(),
    )
    assert result == date(2026, 9, 5)


def test_estimate_payment_date_basic_offset() -> None:
    result = estimate_payment_date(
        usage_date=date(2026, 9, 5),
        closing_day=15,
        closing_day_shift_direction="earlier",
        closing_day_exclusions=frozenset(),
        payment_month_offset=1,
        payment_day=10,
        payment_day_shift_direction="later",
        payment_day_exclusions=frozenset(),
    )
    assert result == date(2026, 10, 10)


def test_estimate_payment_date_usage_after_closing_day_rolls_to_next_month() -> None:
    # Usage on the 22nd with a closing day of 15 falls after this month's cutoff,
    # so it is settled by *next* month's closing day (Oct 15), not this month's.
    result = estimate_payment_date(
        usage_date=date(2026, 9, 22),
        closing_day=15,
        closing_day_shift_direction="later",
        closing_day_exclusions=frozenset(),
        payment_month_offset=1,
        payment_day=13,
        payment_day_shift_direction="later",
        payment_day_exclusions=frozenset(),
    )
    # Closing: Oct 15, 2026. Payment target month: Oct + 1 offset = Nov, day 13.
    assert result == date(2026, 11, 13)


def test_estimate_payment_date_usage_on_closing_day_stays_in_same_month() -> None:
    result = estimate_payment_date(
        usage_date=date(2026, 9, 15),
        closing_day=15,
        closing_day_shift_direction="later",
        closing_day_exclusions=frozenset(),
        payment_month_offset=1,
        payment_day=13,
        payment_day_shift_direction="later",
        payment_day_exclusions=frozenset(),
    )
    # Usage lands exactly on the cutoff, so it still closes within September.
    assert result == date(2026, 10, 13)


def test_estimate_payment_date_rollover_crosses_year_boundary() -> None:
    result = estimate_payment_date(
        usage_date=date(2026, 12, 20),
        closing_day=15,
        closing_day_shift_direction="later",
        closing_day_exclusions=frozenset(),
        payment_month_offset=1,
        payment_day=5,
        payment_day_shift_direction="later",
        payment_day_exclusions=frozenset(),
    )
    # Usage after Dec 15 rolls to the Jan 2027 closing date; +1 month payment is Feb 2027.
    assert result == date(2027, 2, 5)


def test_estimate_payment_date_rollover_respects_clamped_closing_day() -> None:
    # closing_day=31 in a 30-day month (September) clamps to Sep 30 as the cutoff,
    # so usage on the 30th still closes within September, not October.
    result = estimate_payment_date(
        usage_date=date(2026, 9, 30),
        closing_day=31,
        closing_day_shift_direction="later",
        closing_day_exclusions=frozenset(),
        payment_month_offset=0,
        payment_day=10,
        payment_day_shift_direction="later",
        payment_day_exclusions=frozenset(),
    )
    assert result == date(2026, 9, 10)


def test_estimate_payment_date_crosses_year_boundary() -> None:
    result = estimate_payment_date(
        usage_date=date(2026, 12, 20),
        closing_day=31,
        closing_day_shift_direction="earlier",
        closing_day_exclusions=frozenset(),
        payment_month_offset=1,
        payment_day=31,
        payment_day_shift_direction="earlier",
        payment_day_exclusions=frozenset({"nonexistent_day"}),
    )
    # closing: Dec 31, 2026 (exists). payment target month: Jan 2027, day 31
    # does not exist -> clamps to 31... January has 31 days, so it exists.
    assert result == date(2027, 1, 31)
