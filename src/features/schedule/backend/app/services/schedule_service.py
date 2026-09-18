from __future__ import annotations

from datetime import date, time

from app.errors import CompletionNotAllowedError, InvalidInputError, NotFoundError
from app.logger import write
from app.repos import (
    ScheduleRow,
    get_schedule,
    insert_schedule,
    list_schedules_overlapping,
    logical_delete_schedule,
    update_schedule,
    update_schedule_completion,
)
from app.services.category_service import format_time, require_own_active_category


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed if trimmed != "" else None


def _range_ok(
    granularity: str,
    start_date: date,
    end_date: date,
    start_time: time | None,
    end_time: time | None,
) -> bool:
    if end_date < start_date:
        return False
    if end_date > start_date:
        return True
    if granularity == "day":
        return True
    if start_time is None or end_time is None:
        return False
    return end_time >= start_time


def _validate_payload(
    title: str,
    kind: str,
    granularity: str,
    start_date: date,
    end_date: date,
    start_time: time | None,
    end_time: time | None,
) -> str:
    trimmed = title.strip()
    if trimmed == "":
        raise InvalidInputError("タイトルが空")
    if kind not in ("event", "todo"):
        raise InvalidInputError("種別不正")
    if granularity not in ("day", "time"):
        raise InvalidInputError("粒度不正")
    if granularity == "day":
        if start_time is not None or end_time is not None:
            raise InvalidInputError("日単位に時刻がある")
    else:
        if start_time is None or end_time is None:
            raise InvalidInputError("時間単位に時刻がない")
    if not _range_ok(granularity, start_date, end_date, start_time, end_time):
        raise InvalidInputError("終了が開始より前")
    return trimmed


def _completed_for_kind(kind: str, previous: ScheduleRow | None) -> bool | None:
    if kind == "event":
        return None
    if previous is None:
        return False
    if previous.kind == "todo":
        return bool(previous.is_completed)
    return False


def _body(row: ScheduleRow) -> dict[str, object]:
    return {
        "id": row.id,
        "title": row.title,
        "location": row.location,
        "detail": row.detail,
        "kind": row.kind,
        "granularity": row.granularity,
        "start_date": row.start_date.isoformat(),
        "end_date": row.end_date.isoformat(),
        "start_time": format_time(row.start_time),
        "end_time": format_time(row.end_time),
        "category_id": row.category_id,
        "is_completed": row.is_completed,
        "routine_id": row.routine_id,
        "needs_notification": row.needs_notification,
    }


def list_for_range(user_id: int, start_date: date, end_date: date) -> list[dict[str, object]]:
    write(
        "INF",
        f"スケジュール一覧要求 user_id={user_id} start_date={start_date.isoformat()} "
        f"end_date={end_date.isoformat()}",
    )
    if end_date < start_date:
        write("WRN", f"スケジュール一覧失敗 user_id={user_id} 理由=終了が開始より前")
        raise InvalidInputError("終了が開始より前")
    items = [_body(row) for row in list_schedules_overlapping(user_id, start_date, end_date)]
    write("INF", f"スケジュール一覧成功 user_id={user_id} count={len(items)}")
    return items


def add_schedule(
    user_id: int,
    title: str,
    location: str | None,
    detail: str | None,
    kind: str,
    granularity: str,
    start_date: date,
    end_date: date,
    start_time: time | None,
    end_time: time | None,
    category_id: int,
    needs_notification: bool,
) -> dict[str, object]:
    write(
        "INF",
        f"スケジュール追加要求 user_id={user_id} title={title} kind={kind} "
        f"granularity={granularity} start_date={start_date.isoformat()} "
        f"end_date={end_date.isoformat()} start_time={format_time(start_time)} "
        f"end_time={format_time(end_time)} category_id={category_id} "
        f"needs_notification={needs_notification}",
    )
    try:
        trimmed = _validate_payload(
            title, kind, granularity, start_date, end_date, start_time, end_time
        )
        require_own_active_category(user_id, category_id)
    except InvalidInputError as exc:
        write("WRN", f"スケジュール追加失敗 user_id={user_id} 理由={exc}")
        raise
    except NotFoundError:
        write("WRN", f"スケジュール追加失敗 user_id={user_id} category_id={category_id} 理由=カテゴリ対象なし")
        raise
    loc = _optional_text(location)
    det = _optional_text(detail)
    completed = _completed_for_kind(kind, None)
    row = insert_schedule(
        user_id,
        category_id,
        trimmed,
        loc,
        det,
        kind,
        granularity,
        start_date,
        end_date,
        start_time,
        end_time,
        completed,
        needs_notification,
    )
    write("INF", f"スケジュール追加成功 user_id={user_id} schedule_id={row.id}")
    return _body(row)


def change_schedule(
    user_id: int,
    schedule_id: int,
    title: str,
    location: str | None,
    detail: str | None,
    kind: str,
    granularity: str,
    start_date: date,
    end_date: date,
    start_time: time | None,
    end_time: time | None,
    category_id: int,
    needs_notification: bool,
) -> dict[str, object]:
    write(
        "INF",
        f"スケジュール更新要求 user_id={user_id} schedule_id={schedule_id} title={title} "
        f"kind={kind} granularity={granularity} start_date={start_date.isoformat()} "
        f"end_date={end_date.isoformat()} start_time={format_time(start_time)} "
        f"end_time={format_time(end_time)} category_id={category_id} "
        f"needs_notification={needs_notification}",
    )
    existing = get_schedule(user_id, schedule_id)
    if existing is None or existing.is_deleted:
        write("WRN", f"スケジュール更新失敗 user_id={user_id} schedule_id={schedule_id} 理由=対象なし")
        raise NotFoundError()
    try:
        trimmed = _validate_payload(
            title, kind, granularity, start_date, end_date, start_time, end_time
        )
        require_own_active_category(user_id, category_id)
    except InvalidInputError as exc:
        write("WRN", f"スケジュール更新失敗 user_id={user_id} schedule_id={schedule_id} 理由={exc}")
        raise
    except NotFoundError:
        write(
            "WRN",
            f"スケジュール更新失敗 user_id={user_id} schedule_id={schedule_id} "
            f"category_id={category_id} 理由=カテゴリ対象なし",
        )
        raise
    loc = _optional_text(location)
    det = _optional_text(detail)
    completed = _completed_for_kind(kind, existing)
    update_schedule(
        schedule_id,
        user_id,
        category_id,
        trimmed,
        loc,
        det,
        kind,
        granularity,
        start_date,
        end_date,
        start_time,
        end_time,
        completed,
        needs_notification,
    )
    updated = get_schedule(user_id, schedule_id)
    assert updated is not None
    write("INF", f"スケジュール更新成功 user_id={user_id} schedule_id={schedule_id}")
    return _body(updated)


def change_completion(user_id: int, schedule_id: int, is_completed: bool) -> dict[str, object]:
    write(
        "INF",
        f"実施状態更新要求 user_id={user_id} schedule_id={schedule_id} is_completed={is_completed}",
    )
    existing = get_schedule(user_id, schedule_id)
    if existing is None or existing.is_deleted:
        write("WRN", f"実施状態更新失敗 user_id={user_id} schedule_id={schedule_id} 理由=対象なし")
        raise NotFoundError()
    if existing.kind != "todo":
        write("WRN", f"実施状態更新失敗 user_id={user_id} schedule_id={schedule_id} 理由=予定への実施状態変更")
        raise CompletionNotAllowedError()
    update_schedule_completion(schedule_id, user_id, is_completed)
    updated = get_schedule(user_id, schedule_id)
    assert updated is not None
    write("INF", f"実施状態更新成功 user_id={user_id} schedule_id={schedule_id}")
    return _body(updated)


def remove_schedule(user_id: int, schedule_id: int) -> None:
    write("INF", f"スケジュール削除要求 user_id={user_id} schedule_id={schedule_id}")
    existing = get_schedule(user_id, schedule_id)
    if existing is None or existing.is_deleted:
        write("WRN", f"スケジュール削除失敗 user_id={user_id} schedule_id={schedule_id} 理由=対象なし")
        raise NotFoundError()
    logical_delete_schedule(schedule_id, user_id)
    write("INF", f"スケジュール削除成功 user_id={user_id} schedule_id={schedule_id}")
