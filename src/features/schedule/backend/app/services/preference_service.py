from __future__ import annotations

from app.errors import InvalidInputError
from app.logger import write
from app.repos import (
    get_category,
    get_preference,
    list_hidden_category_ids,
    replace_hidden_categories,
    upsert_preference,
)

DEFAULT_WEEK = "sunday"


def _body(week_starts_on: str, show_deleted: bool, hidden_ids: list[int]) -> dict[str, object]:
    return {
        "week_starts_on": week_starts_on,
        "show_deleted": show_deleted,
        "hidden_category_ids": hidden_ids,
    }


def get_for_user(user_id: int) -> dict[str, object]:
    write("INF", f"表示設定取得要求 user_id={user_id}")
    row = get_preference(user_id)
    hidden = list_hidden_category_ids(user_id)
    if row is None:
        write("INF", f"表示設定取得成功 user_id={user_id} 初期値")
        return _body(DEFAULT_WEEK, False, hidden)
    write("INF", f"表示設定取得成功 user_id={user_id} week_starts_on={row.week_starts_on}")
    return _body(row.week_starts_on, row.show_deleted, hidden)


def save_for_user(
    user_id: int,
    week_starts_on: str,
    show_deleted: bool,
    hidden_category_ids: list[int],
) -> dict[str, object]:
    write(
        "INF",
        f"表示設定更新要求 user_id={user_id} week_starts_on={week_starts_on} "
        f"show_deleted={show_deleted} hidden_category_ids={hidden_category_ids}",
    )
    if week_starts_on not in ("sunday", "monday"):
        write("WRN", f"表示設定更新失敗 user_id={user_id} 理由=week_starts_on不正")
        raise InvalidInputError("week_starts_on不正")
    unique_ids: list[int] = []
    seen: set[int] = set()
    for category_id in hidden_category_ids:
        if category_id in seen:
            continue
        seen.add(category_id)
        category = get_category(user_id, category_id)
        if category is None:
            write(
                "WRN",
                f"表示設定更新失敗 user_id={user_id} category_id={category_id} 理由=他ユーザまたは存在しないカテゴリ",
            )
            raise InvalidInputError("カテゴリID不正")
        unique_ids.append(category_id)
    upsert_preference(user_id, week_starts_on, show_deleted)
    replace_hidden_categories(user_id, unique_ids)
    write("INF", f"表示設定更新成功 user_id={user_id}")
    return _body(week_starts_on, show_deleted, unique_ids)
