from __future__ import annotations

from datetime import date

import jpholiday


def is_holiday(day: date) -> bool:
    """日本の国民の祝日（振替休日を含む）かを返す。外部の祝日 API は呼ばない。ユーザ休日は扱わない。"""
    return bool(jpholiday.is_holiday(day))
