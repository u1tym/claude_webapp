from __future__ import annotations

import re
from datetime import date, datetime, time

from psycopg2 import errorcodes
from psycopg2 import IntegrityError

from app.errors import DuplicateError, InvalidInputError, NotFoundError
from app.logger import write
from app.repos import (
    CategoryRow,
    get_category,
    insert_category,
    list_categories,
    logical_delete_category,
    update_category,
)

COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _validate_name_color(name: str, color: str) -> tuple[str, str]:
    trimmed = name.strip()
    if trimmed == "":
        raise InvalidInputError("名称が空")
    if COLOR_PATTERN.fullmatch(color) is None:
        raise InvalidInputError("色形式不正")
    return trimmed, color


def _body(row: CategoryRow) -> dict[str, object]:
    return {
        "id": row.id,
        "name": row.name,
        "color": row.color,
        "is_deleted": row.is_deleted,
    }


def list_for_user(user_id: int, include_deleted: bool) -> list[dict[str, object]]:
    write("INF", f"カテゴリ一覧要求 user_id={user_id} include_deleted={include_deleted}")
    items = [_body(row) for row in list_categories(user_id, include_deleted)]
    write("INF", f"カテゴリ一覧成功 user_id={user_id} count={len(items)}")
    return items


def add_category(user_id: int, name: str, color: str) -> dict[str, object]:
    write("INF", f"カテゴリ追加要求 user_id={user_id} name={name} color={color}")
    try:
        trimmed, color_ok = _validate_name_color(name, color)
    except InvalidInputError as exc:
        write("WRN", f"カテゴリ追加失敗 user_id={user_id} 理由={exc}")
        raise
    try:
        row = insert_category(user_id, trimmed, color_ok)
    except IntegrityError as exc:
        if getattr(exc, "pgcode", None) != errorcodes.UNIQUE_VIOLATION:
            raise
        write("WRN", f"カテゴリ追加失敗 user_id={user_id} name={trimmed} 理由=名称重複")
        raise DuplicateError() from None
    write("INF", f"カテゴリ追加成功 user_id={user_id} category_id={row.id}")
    return _body(row)


def change_category(user_id: int, category_id: int, name: str, color: str) -> dict[str, object]:
    write(
        "INF",
        f"カテゴリ更新要求 user_id={user_id} category_id={category_id} name={name} color={color}",
    )
    try:
        trimmed, color_ok = _validate_name_color(name, color)
    except InvalidInputError as exc:
        write("WRN", f"カテゴリ更新失敗 user_id={user_id} category_id={category_id} 理由={exc}")
        raise
    row = get_category(user_id, category_id)
    if row is None or row.is_deleted:
        write("WRN", f"カテゴリ更新失敗 user_id={user_id} category_id={category_id} 理由=対象なし")
        raise NotFoundError()
    try:
        update_category(category_id, user_id, trimmed, color_ok)
    except IntegrityError as exc:
        if getattr(exc, "pgcode", None) != errorcodes.UNIQUE_VIOLATION:
            raise
        write("WRN", f"カテゴリ更新失敗 user_id={user_id} category_id={category_id} 理由=名称重複")
        raise DuplicateError() from None
    updated = get_category(user_id, category_id)
    assert updated is not None
    write("INF", f"カテゴリ更新成功 user_id={user_id} category_id={category_id}")
    return _body(updated)


def remove_category(user_id: int, category_id: int) -> None:
    write("INF", f"カテゴリ削除要求 user_id={user_id} category_id={category_id}")
    row = get_category(user_id, category_id)
    if row is None or row.is_deleted:
        write("WRN", f"カテゴリ削除失敗 user_id={user_id} category_id={category_id} 理由=対象なし")
        raise NotFoundError()
    logical_delete_category(category_id, user_id)
    write("INF", f"カテゴリ削除成功 user_id={user_id} category_id={category_id}")


def require_own_active_category(user_id: int, category_id: int) -> CategoryRow:
    row = get_category(user_id, category_id)
    if row is None or row.is_deleted:
        raise NotFoundError()
    return row


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise InvalidInputError("日付不正") from exc


def parse_time(value: str) -> time:
    try:
        parsed = datetime.strptime(value, "%H:%M")
    except ValueError as exc:
        raise InvalidInputError("時刻不正") from exc
    return parsed.time().replace(second=0, microsecond=0)


def format_time(value: time | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%H:%M")
