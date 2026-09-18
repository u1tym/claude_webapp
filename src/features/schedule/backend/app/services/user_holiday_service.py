from __future__ import annotations

from datetime import date

from psycopg2 import errorcodes
from psycopg2 import IntegrityError

from app.errors import DuplicateError, InvalidInputError, NotFoundError
from app.logger import write
from app.repos import (
    UserHolidayRow,
    get_user_holiday,
    insert_user_holiday,
    list_user_holidays,
    logical_delete_user_holiday,
    update_user_holiday,
)


def _body(row: UserHolidayRow) -> dict[str, object]:
    return {
        "id": row.id,
        "holiday_date": row.holiday_date.isoformat(),
        "name": row.name,
    }


def list_for_user(
    user_id: int,
    start_date: date | None,
    end_date: date | None,
) -> list[dict[str, object]]:
    write(
        "INF",
        f"ユーザ休日一覧要求 user_id={user_id} start_date={start_date} end_date={end_date}",
    )
    if (start_date is None) != (end_date is None):
        write("WRN", f"ユーザ休日一覧失敗 user_id={user_id} 理由=範囲の片方だけ")
        raise InvalidInputError("範囲の片方だけ")
    if start_date is not None and end_date is not None and end_date < start_date:
        write("WRN", f"ユーザ休日一覧失敗 user_id={user_id} 理由=終了が開始より前")
        raise InvalidInputError("終了が開始より前")
    items = [_body(row) for row in list_user_holidays(user_id, start_date, end_date)]
    write("INF", f"ユーザ休日一覧成功 user_id={user_id} count={len(items)}")
    return items


def add_user_holiday(user_id: int, holiday_date: date, name: str) -> dict[str, object]:
    write(
        "INF",
        f"ユーザ休日追加要求 user_id={user_id} holiday_date={holiday_date.isoformat()} name={name}",
    )
    trimmed = name.strip()
    if trimmed == "":
        write("WRN", f"ユーザ休日追加失敗 user_id={user_id} 理由=名称が空")
        raise InvalidInputError("名称が空")
    try:
        row = insert_user_holiday(user_id, holiday_date, trimmed)
    except IntegrityError as exc:
        if getattr(exc, "pgcode", None) != errorcodes.UNIQUE_VIOLATION:
            raise
        write(
            "WRN",
            f"ユーザ休日追加失敗 user_id={user_id} holiday_date={holiday_date.isoformat()} 理由=年月日重複",
        )
        raise DuplicateError() from None
    write("INF", f"ユーザ休日追加成功 user_id={user_id} user_holiday_id={row.id}")
    return _body(row)


def change_user_holiday(
    user_id: int,
    holiday_id: int,
    holiday_date: date,
    name: str,
) -> dict[str, object]:
    write(
        "INF",
        f"ユーザ休日更新要求 user_id={user_id} user_holiday_id={holiday_id} "
        f"holiday_date={holiday_date.isoformat()} name={name}",
    )
    trimmed = name.strip()
    if trimmed == "":
        write("WRN", f"ユーザ休日更新失敗 user_id={user_id} user_holiday_id={holiday_id} 理由=名称が空")
        raise InvalidInputError("名称が空")
    existing = get_user_holiday(user_id, holiday_id)
    if existing is None or existing.is_deleted:
        write("WRN", f"ユーザ休日更新失敗 user_id={user_id} user_holiday_id={holiday_id} 理由=対象なし")
        raise NotFoundError()
    try:
        update_user_holiday(holiday_id, user_id, holiday_date, trimmed)
    except IntegrityError as exc:
        if getattr(exc, "pgcode", None) != errorcodes.UNIQUE_VIOLATION:
            raise
        write(
            "WRN",
            f"ユーザ休日更新失敗 user_id={user_id} user_holiday_id={holiday_id} 理由=年月日重複",
        )
        raise DuplicateError() from None
    updated = get_user_holiday(user_id, holiday_id)
    assert updated is not None
    write("INF", f"ユーザ休日更新成功 user_id={user_id} user_holiday_id={holiday_id}")
    return _body(updated)


def remove_user_holiday(user_id: int, holiday_id: int) -> None:
    write("INF", f"ユーザ休日削除要求 user_id={user_id} user_holiday_id={holiday_id}")
    existing = get_user_holiday(user_id, holiday_id)
    if existing is None or existing.is_deleted:
        write("WRN", f"ユーザ休日削除失敗 user_id={user_id} user_holiday_id={holiday_id} 理由=対象なし")
        raise NotFoundError()
    logical_delete_user_holiday(holiday_id, user_id)
    write("INF", f"ユーザ休日削除成功 user_id={user_id} user_holiday_id={holiday_id}")
