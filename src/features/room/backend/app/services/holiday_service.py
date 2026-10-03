from __future__ import annotations

from datetime import date

import jpholiday

from app.repos import is_user_holiday


def is_holiday(day: date, user_id: int | None = None) -> bool:
    """日本の国民の祝日（振替休日を含む）、または user_id のユーザ休日かを返す。外部の祝日 API は呼ばない。"""
    if bool(jpholiday.is_holiday(day)):
        return True
    return user_id is not None and is_user_holiday(user_id, day)
