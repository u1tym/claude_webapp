from __future__ import annotations

from datetime import date

import jpholiday

from app.errors import InvalidInputError
from app.logger import write


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
