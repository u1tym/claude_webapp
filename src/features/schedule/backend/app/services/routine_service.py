from __future__ import annotations

import calendar
from datetime import date, timedelta

import jpholiday

from app.errors import InvalidInputError, NotFoundError
from app.logger import write
from app.repos import (
    RoutineRow,
    exists_routine_in_year_month,
    get_category,
    get_routine,
    insert_routine,
    insert_schedule,
    list_routines,
    logical_delete_routine,
    update_routine,
)
from app.services.schedule_service import _body as schedule_body
from app.services.schedule_service import _optional_text

WEEKDAYS = (
    "sunday",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
)
EXCLUSIONS = ("holiday",) + WEEKDAYS
DATE_RULES = ("last_day", "day_of_month")
WEEKDAY_RULES = ("nth", "nth_from_last")
SHIFT_DIRECTIONS = ("earlier", "later")
_PY_WEEKDAY = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
_NAME_BY_PY = {value: key for key, value in _PY_WEEKDAY.items()}


def _body(row: RoutineRow) -> dict[str, object]:
    return {
        "id": row.id,
        "title": row.title,
        "detail": row.detail,
        "kind": row.kind,
        "category_id": row.category_id,
        "occurrence_type": row.occurrence_type,
        "date_rule": row.date_rule,
        "day_of_month": row.day_of_month,
        "weekday_rule": row.weekday_rule,
        "weekday_n": row.weekday_n,
        "weekday": row.weekday,
        "adjust_excluded": row.adjust_excluded,
        "shift_direction": row.shift_direction,
        "needs_notification": row.needs_notification,
        "months": list(row.months),
        "exclusions": list(row.exclusions),
    }


def _unique_sorted_ints(values: list[int], low: int, high: int, empty_reason: str) -> list[int]:
    if len(values) == 0:
        raise InvalidInputError(empty_reason)
    seen: set[int] = set()
    out: list[int] = []
    for value in values:
        if value < low or value > high:
            raise InvalidInputError("範囲外")
        if value in seen:
            raise InvalidInputError("重複")
        seen.add(value)
        out.append(value)
    out.sort()
    return out


def _unique_sorted_exclusions(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in EXCLUSIONS:
            raise InvalidInputError("除外対象不正")
        if value in seen:
            raise InvalidInputError("重複")
        seen.add(value)
        out.append(value)
    out.sort()
    return out


def _validate_fields(
    title: str,
    kind: str,
    occurrence_type: str,
    date_rule: str | None,
    day_of_month: int | None,
    weekday_rule: str | None,
    weekday_n: int | None,
    weekday: str | None,
    adjust_excluded: bool,
    shift_direction: str | None,
    months: list[int],
    exclusions: list[str],
) -> tuple[
    str,
    str | None,
    int | None,
    str | None,
    int | None,
    str | None,
    str | None,
    list[int],
    list[str],
]:
    trimmed = title.strip()
    if trimmed == "":
        raise InvalidInputError("タイトルが空")
    if kind not in ("event", "todo"):
        raise InvalidInputError("種別不正")
    if occurrence_type not in ("date", "weekday"):
        raise InvalidInputError("適用日タイプ不正")
    months_ok = _unique_sorted_ints(months, 1, 12, "反映月が空")
    if occurrence_type == "date":
        if date_rule not in DATE_RULES:
            raise InvalidInputError("日付の決め方が無い")
        if weekday_rule is not None or weekday_n is not None or weekday is not None:
            raise InvalidInputError("日付指定なのに曜日項目がある")
        if date_rule == "last_day":
            if day_of_month is not None:
                raise InvalidInputError("月末日なのに日がある")
            day_ok: int | None = None
        else:
            if day_of_month is None or day_of_month < 1 or day_of_month > 31:
                raise InvalidInputError("毎月X日が不正")
            day_ok = day_of_month
        weekday_rule_ok = None
        weekday_n_ok = None
        weekday_ok = None
        date_rule_ok = date_rule
    else:
        if weekday_rule not in WEEKDAY_RULES:
            raise InvalidInputError("曜日の決め方が無い")
        if weekday_n is None or weekday_n < 1 or weekday_n > 5:
            raise InvalidInputError("Nが不正")
        if weekday not in WEEKDAYS:
            raise InvalidInputError("曜日が不正")
        if date_rule is not None or day_of_month is not None:
            raise InvalidInputError("曜日指定なのに日付項目がある")
        date_rule_ok = None
        day_ok = None
        weekday_rule_ok = weekday_rule
        weekday_n_ok = weekday_n
        weekday_ok = weekday
    if not adjust_excluded:
        if shift_direction is not None or len(exclusions) > 0:
            raise InvalidInputError("除外調整が無なのに除外がある")
        shift_ok = None
        exclusions_ok: list[str] = []
    else:
        if shift_direction not in SHIFT_DIRECTIONS:
            raise InvalidInputError("ずらしかたが無い")
        exclusions_ok = _unique_sorted_exclusions(exclusions)
        if len(exclusions_ok) == 0:
            raise InvalidInputError("除外対象が空")
        shift_ok = shift_direction
    return (
        trimmed,
        date_rule_ok,
        day_ok,
        weekday_rule_ok,
        weekday_n_ok,
        weekday_ok,
        shift_ok,
        months_ok,
        exclusions_ok,
    )


def base_date(
    year: int,
    month: int,
    occurrence_type: str,
    date_rule: str | None,
    day_of_month: int | None,
    weekday_rule: str | None,
    weekday_n: int | None,
    weekday: str | None,
) -> date | None:
    last_day = calendar.monthrange(year, month)[1]
    if occurrence_type == "date":
        if date_rule == "last_day":
            return date(year, month, last_day)
        if date_rule == "day_of_month" and day_of_month is not None:
            if day_of_month > last_day:
                return None
            return date(year, month, day_of_month)
        return None
    if weekday is None or weekday_n is None or weekday_rule is None:
        return None
    target = _PY_WEEKDAY[weekday]
    if weekday_rule == "nth":
        first = date(year, month, 1)
        delta = (target - first.weekday()) % 7
        day_num = 1 + delta + 7 * (weekday_n - 1)
        if day_num > last_day:
            return None
        return date(year, month, day_num)
    last = date(year, month, last_day)
    delta = (last.weekday() - target) % 7
    found = last - timedelta(days=delta)
    found = found - timedelta(days=7 * (weekday_n - 1))
    if found.month != month:
        return None
    return found


def apply_date(
    origin: date | None,
    adjust_excluded: bool,
    shift_direction: str | None,
    exclusions: list[str] | tuple[str, ...],
) -> date | None:
    if origin is None:
        return None
    if not adjust_excluded:
        return origin
    excluded = set(exclusions)
    current = origin
    for _ in range(32):
        if not _is_excluded(current, excluded):
            return current
        if shift_direction == "earlier":
            current = current - timedelta(days=1)
        elif shift_direction == "later":
            current = current + timedelta(days=1)
        else:
            return None
    return None


def _is_excluded(day: date, excluded: set[str]) -> bool:
    if "holiday" in excluded and bool(jpholiday.is_holiday(day)):
        return True
    return _NAME_BY_PY[day.weekday()] in excluded


def list_for_user(user_id: int) -> list[dict[str, object]]:
    write("INF", f"ルーチン一覧要求 user_id={user_id}")
    items = [_body(row) for row in list_routines(user_id)]
    write("INF", f"ルーチン一覧成功 user_id={user_id} count={len(items)}")
    return items


def add_routine(
    user_id: int,
    title: str,
    detail: str | None,
    kind: str,
    category_id: int,
    occurrence_type: str,
    date_rule: str | None,
    day_of_month: int | None,
    weekday_rule: str | None,
    weekday_n: int | None,
    weekday: str | None,
    adjust_excluded: bool,
    shift_direction: str | None,
    needs_notification: bool,
    months: list[int],
    exclusions: list[str],
) -> dict[str, object]:
    write(
        "INF",
        f"ルーチン追加要求 user_id={user_id} title={title} kind={kind} "
        f"category_id={category_id} occurrence_type={occurrence_type} "
        f"date_rule={date_rule} day_of_month={day_of_month} weekday_rule={weekday_rule} "
        f"weekday_n={weekday_n} weekday={weekday} months={months} "
        f"adjust_excluded={adjust_excluded} shift_direction={shift_direction} "
        f"exclusions={exclusions} needs_notification={needs_notification}",
    )
    try:
        (
            trimmed,
            date_rule_ok,
            day_ok,
            weekday_rule_ok,
            weekday_n_ok,
            weekday_ok,
            shift_ok,
            months_ok,
            exclusions_ok,
        ) = _validate_fields(
            title,
            kind,
            occurrence_type,
            date_rule,
            day_of_month,
            weekday_rule,
            weekday_n,
            weekday,
            adjust_excluded,
            shift_direction,
            months,
            exclusions,
        )
        category = get_category(user_id, category_id)
        if category is None or category.is_deleted or category.user_id != user_id:
            write("WRN", f"ルーチン追加失敗 user_id={user_id} category_id={category_id} 理由=カテゴリ対象なし")
            raise NotFoundError()
    except InvalidInputError as exc:
        write("WRN", f"ルーチン追加失敗 user_id={user_id} 理由={exc}")
        raise
    row = insert_routine(
        user_id,
        category_id,
        trimmed,
        _optional_text(detail),
        kind,
        occurrence_type,
        date_rule_ok,
        day_ok,
        weekday_rule_ok,
        weekday_n_ok,
        weekday_ok,
        adjust_excluded,
        shift_ok,
        needs_notification,
        months_ok,
        exclusions_ok,
    )
    write("INF", f"ルーチン追加成功 user_id={user_id} routine_id={row.id}")
    return _body(row)


def change_routine(
    user_id: int,
    routine_id: int,
    title: str,
    detail: str | None,
    kind: str,
    category_id: int,
    occurrence_type: str,
    date_rule: str | None,
    day_of_month: int | None,
    weekday_rule: str | None,
    weekday_n: int | None,
    weekday: str | None,
    adjust_excluded: bool,
    shift_direction: str | None,
    needs_notification: bool,
    months: list[int],
    exclusions: list[str],
) -> dict[str, object]:
    write(
        "INF",
        f"ルーチン更新要求 user_id={user_id} routine_id={routine_id} title={title} kind={kind} "
        f"category_id={category_id} occurrence_type={occurrence_type} "
        f"date_rule={date_rule} day_of_month={day_of_month} weekday_rule={weekday_rule} "
        f"weekday_n={weekday_n} weekday={weekday} months={months} "
        f"adjust_excluded={adjust_excluded} shift_direction={shift_direction} "
        f"exclusions={exclusions} needs_notification={needs_notification}",
    )
    existing = get_routine(user_id, routine_id)
    if existing is None or existing.is_deleted:
        write("WRN", f"ルーチン更新失敗 user_id={user_id} routine_id={routine_id} 理由=対象なし")
        raise NotFoundError()
    try:
        (
            trimmed,
            date_rule_ok,
            day_ok,
            weekday_rule_ok,
            weekday_n_ok,
            weekday_ok,
            shift_ok,
            months_ok,
            exclusions_ok,
        ) = _validate_fields(
            title,
            kind,
            occurrence_type,
            date_rule,
            day_of_month,
            weekday_rule,
            weekday_n,
            weekday,
            adjust_excluded,
            shift_direction,
            months,
            exclusions,
        )
        category = get_category(user_id, category_id)
        if category is None or category.is_deleted or category.user_id != user_id:
            write(
                "WRN",
                f"ルーチン更新失敗 user_id={user_id} routine_id={routine_id} "
                f"category_id={category_id} 理由=カテゴリ対象なし",
            )
            raise NotFoundError()
    except InvalidInputError as exc:
        write("WRN", f"ルーチン更新失敗 user_id={user_id} routine_id={routine_id} 理由={exc}")
        raise
    row = update_routine(
        routine_id,
        user_id,
        category_id,
        trimmed,
        _optional_text(detail),
        kind,
        occurrence_type,
        date_rule_ok,
        day_ok,
        weekday_rule_ok,
        weekday_n_ok,
        weekday_ok,
        adjust_excluded,
        shift_ok,
        needs_notification,
        months_ok,
        exclusions_ok,
    )
    if row is None:
        write("WRN", f"ルーチン更新失敗 user_id={user_id} routine_id={routine_id} 理由=対象なし")
        raise NotFoundError()
    write("INF", f"ルーチン更新成功 user_id={user_id} routine_id={routine_id}")
    return _body(row)


def remove_routine(user_id: int, routine_id: int) -> None:
    write("INF", f"ルーチン削除要求 user_id={user_id} routine_id={routine_id}")
    existing = get_routine(user_id, routine_id)
    if existing is None or existing.is_deleted:
        write("WRN", f"ルーチン削除失敗 user_id={user_id} routine_id={routine_id} 理由=対象なし")
        raise NotFoundError()
    logical_delete_routine(routine_id, user_id)
    write("INF", f"ルーチン削除成功 user_id={user_id} routine_id={routine_id}")


def _require_year_month(year: int, month: int) -> None:
    if month < 1 or month > 12:
        raise InvalidInputError("月が不正")


def _apply_one(user_id: int, row: RoutineRow, year: int, month: int) -> dict[str, object] | None:
    if month not in row.months:
        write(
            "INF",
            f"ルーチン適用スキップ user_id={user_id} routine_id={row.id} "
            f"year={year} month={month} 理由=反映月外",
        )
        return None
    if exists_routine_in_year_month(user_id, row.id, year, month):
        write(
            "INF",
            f"ルーチン適用スキップ user_id={user_id} routine_id={row.id} "
            f"year={year} month={month} 理由=同一ルーチン識別が指定年月に既にある",
        )
        return None
    category = get_category(user_id, row.category_id)
    if category is None or category.is_deleted or category.user_id != user_id:
        write(
            "INF",
            f"ルーチン適用スキップ user_id={user_id} routine_id={row.id} "
            f"year={year} month={month} 理由=カテゴリ対象なし",
        )
        return None
    origin = base_date(
        year,
        month,
        row.occurrence_type,
        row.date_rule,
        row.day_of_month,
        row.weekday_rule,
        row.weekday_n,
        row.weekday,
    )
    target = apply_date(origin, row.adjust_excluded, row.shift_direction, row.exclusions)
    if origin is None or target is None:
        write(
            "INF",
            f"ルーチン適用スキップ user_id={user_id} routine_id={row.id} "
            f"year={year} month={month} 理由={'基準日なし' if origin is None else '適用日なし'}",
        )
        return None
    completed = None if row.kind == "event" else False
    created = insert_schedule(
        user_id,
        row.category_id,
        row.title,
        None,
        row.detail,
        row.kind,
        "day",
        target,
        target,
        None,
        None,
        completed,
        row.needs_notification,
        row.id,
    )
    write(
        "INF",
        f"ルーチン適用成功 user_id={user_id} routine_id={row.id} "
        f"year={year} month={month} schedule_id={created.id} apply_date={target.isoformat()}",
    )
    return schedule_body(created)


def apply_routine(user_id: int, routine_id: int, year: int, month: int) -> list[dict[str, object]]:
    write(
        "INF",
        f"ルーチン適用要求 user_id={user_id} routine_id={routine_id} year={year} month={month}",
    )
    try:
        _require_year_month(year, month)
    except InvalidInputError as exc:
        write(
            "WRN",
            f"ルーチン適用失敗 user_id={user_id} routine_id={routine_id} "
            f"year={year} month={month} 理由={exc}",
        )
        raise
    existing = get_routine(user_id, routine_id)
    if existing is None or existing.is_deleted:
        write(
            "WRN",
            f"ルーチン適用失敗 user_id={user_id} routine_id={routine_id} 理由=対象なし",
        )
        raise NotFoundError()
    created = _apply_one(user_id, existing, year, month)
    items = [] if created is None else [created]
    write(
        "INF",
        f"ルーチン適用完了 user_id={user_id} routine_id={routine_id} "
        f"year={year} month={month} created={len(items)}",
    )
    return items


def apply_all(user_id: int, year: int, month: int) -> list[dict[str, object]]:
    write("INF", f"ルーチン一括適用要求 user_id={user_id} year={year} month={month}")
    try:
        _require_year_month(year, month)
    except InvalidInputError as exc:
        write("WRN", f"ルーチン一括適用失敗 user_id={user_id} year={year} month={month} 理由={exc}")
        raise
    items: list[dict[str, object]] = []
    for row in list_routines(user_id):
        created = _apply_one(user_id, row, year, month)
        if created is not None:
            items.append(created)
    items.sort(
        key=lambda item: (
            0 if item["granularity"] == "day" else 1,
            str(item["start_date"]),
            str(item["start_time"] or ""),
            str(item["end_date"]),
            str(item["end_time"] or ""),
            str(item["title"]),
        )
    )
    write("INF", f"ルーチン一括適用成功 user_id={user_id} year={year} month={month} created={len(items)}")
    return items
