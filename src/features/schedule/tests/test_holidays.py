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
