from __future__ import annotations

from datetime import date

import jpholiday

from app.errors import InvalidInputError
from app.logger import write
from app.repos import list_user_holidays


def list_national_holidays(start_date: date, end_date: date) -> list[dict[str, str]]:
    write(
        "INF",
        f"祝日一覧要求 start_date={start_date.isoformat()} end_date={end_date.isoformat()}",
    )
    if end_date < start_date:
        write("WRN", "祝日一覧失敗 理由=終了が開始より前")
        raise InvalidInputError("終了が開始より前")
    raw = jpholiday.between(start_date, end_date)
    items = [{"date": day.isoformat(), "name": name} for day, name in raw]
    write("INF", f"祝日一覧成功 count={len(items)}")
    return items


def user_holiday_dates(user_id: int, start_date: date, end_date: date) -> frozenset[date]:
    """本人の未削除のユーザ休日の年月日（期間内）を返す。"""
    rows = list_user_holidays(user_id, start_date, end_date)
    return frozenset(row.holiday_date for row in rows)


def is_holiday(day: date, user_dates: frozenset[date] | None = None) -> bool:
    """日本の祝日（振替休日を含む）、または本人のユーザ休日かを返す。外部の祝日 API は呼ばない。"""
    if bool(jpholiday.is_holiday(day)):
        return True
    return user_dates is not None and day in user_dates
