from __future__ import annotations

from datetime import date
from unittest.mock import patch

from app.services.holiday_service import list_national_holidays


def test_holidays_include_substitute_and_sorted() -> None:
    items = list_national_holidays(date(2026, 5, 1), date(2026, 5, 7))
    dates = [item["date"] for item in items]
    assert dates == sorted(dates)
    names_by_date = {item["date"]: item["name"] for item in items}
    assert "2026-05-03" in names_by_date
    assert "2026-05-04" in names_by_date
    assert "2026-05-05" in names_by_date
    assert "2026-05-06" in names_by_date
    assert "振替" in names_by_date["2026-05-06"]


def test_holidays_do_not_call_network() -> None:
    with patch("urllib.request.urlopen") as mocked:
        items = list_national_holidays(date(2026, 1, 1), date(2026, 1, 1))
        mocked.assert_not_called()
    assert items[0]["date"] == "2026-01-01"
    assert items[0]["name"] == "元日"


def test_is_holiday_includes_user_dates() -> None:
    from app.services.holiday_service import is_holiday

    user_dates = frozenset({date(2026, 1, 2)})
    assert is_holiday(date(2026, 1, 1), user_dates) is True  # 日本の祝日
    assert is_holiday(date(2026, 1, 2), user_dates) is True  # ユーザ休日
    assert is_holiday(date(2026, 1, 2), None) is False
    assert is_holiday(date(2026, 1, 2), frozenset({date(2026, 1, 5)})) is False
