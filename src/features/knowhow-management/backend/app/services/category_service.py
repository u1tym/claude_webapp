from __future__ import annotations

from app.errors import DuplicateError, InvalidInputError, NotFoundError
from app.logger import safe_text, write
from app.repos import (
    MajorCategoryRow,
    MiddleCategoryRow,
    cascade_delete_major_category,
    cascade_delete_middle_category,
    get_major_category,
    get_middle_category,
    insert_major_category,
    insert_middle_category,
    list_major_categories,
    list_middle_categories,
    major_category_name_exists,
    middle_category_name_exists,
    update_major_category_name,
    update_middle_category_name,
)


def _validate_name(name: str) -> str:
    trimmed = name.strip()
    if trimmed == "":
        raise InvalidInputError("名称が空")
    return trimmed


def _major_body(row: MajorCategoryRow) -> dict[str, object]:
    return {"id": row.id, "name": row.name, "display_order": row.display_order}


def _middle_body(row: MiddleCategoryRow) -> dict[str, object]:
    return {
        "id": row.id,
        "major_category_id": row.major_category_id,
        "name": row.name,
        "display_order": row.display_order,
    }


def list_majors(user_id: int) -> list[dict[str, object]]:
    write("INF", f"大項目一覧要求 user_id={user_id}")
    items = [_major_body(row) for row in list_major_categories(user_id)]
    write("INF", f"大項目一覧成功 user_id={user_id} count={len(items)}")
    return items


def create_major(user_id: int, name: str) -> dict[str, object]:
    write("INF", f"大項目登録要求 user_id={user_id} name={safe_text(name)}")
    trimmed = _validate_name(name)
    if major_category_name_exists(user_id, trimmed):
        write("WRN", f"大項目登録失敗 user_id={user_id} name={safe_text(trimmed)} 理由=重複")
        raise DuplicateError
    row = insert_major_category(user_id, trimmed)
    write("INF", f"大項目登録成功 user_id={user_id} major_category_id={row.id}")
    return _major_body(row)


def rename_major(user_id: int, major_category_id: int, name: str) -> dict[str, object]:
    write("INF", f"大項目名称変更要求 user_id={user_id} major_category_id={major_category_id}")
    existing = get_major_category(user_id, major_category_id)
    if existing is None:
        write("WRN", f"大項目名称変更失敗 user_id={user_id} major_category_id={major_category_id} 理由=対象なし")
        raise NotFoundError
    trimmed = _validate_name(name)
    if major_category_name_exists(user_id, trimmed, exclude_id=major_category_id):
        write(
            "WRN",
            f"大項目名称変更失敗 user_id={user_id} major_category_id={major_category_id} 理由=重複",
        )
        raise DuplicateError
    update_major_category_name(major_category_id, user_id, trimmed)
    updated = get_major_category(user_id, major_category_id)
    assert updated is not None
    write("INF", f"大項目名称変更成功 user_id={user_id} major_category_id={major_category_id}")
    return _major_body(updated)


def remove_major(user_id: int, major_category_id: int) -> None:
    write("INF", f"大項目削除要求 user_id={user_id} major_category_id={major_category_id}")
    existing = get_major_category(user_id, major_category_id)
    if existing is None:
        write("WRN", f"大項目削除失敗 user_id={user_id} major_category_id={major_category_id} 理由=対象なし")
        raise NotFoundError
    cascade_delete_major_category(major_category_id, user_id)
    write("INF", f"大項目削除成功 user_id={user_id} major_category_id={major_category_id}")


def list_middles(user_id: int, major_category_id: int) -> list[dict[str, object]]:
    write("INF", f"中項目一覧要求 user_id={user_id} major_category_id={major_category_id}")
    if get_major_category(user_id, major_category_id) is None:
        write("WRN", f"中項目一覧失敗 user_id={user_id} major_category_id={major_category_id} 理由=対象なし")
        raise NotFoundError
    items = [_middle_body(row) for row in list_middle_categories(user_id, major_category_id)]
    write("INF", f"中項目一覧成功 user_id={user_id} major_category_id={major_category_id} count={len(items)}")
    return items


def create_middle(user_id: int, major_category_id: int, name: str) -> dict[str, object]:
    write("INF", f"中項目登録要求 user_id={user_id} major_category_id={major_category_id} name={safe_text(name)}")
    if get_major_category(user_id, major_category_id) is None:
        write("WRN", f"中項目登録失敗 user_id={user_id} major_category_id={major_category_id} 理由=対象なし")
        raise NotFoundError
    trimmed = _validate_name(name)
    if middle_category_name_exists(major_category_id, trimmed):
        write(
            "WRN",
            f"中項目登録失敗 user_id={user_id} major_category_id={major_category_id} name={safe_text(trimmed)} 理由=重複",
        )
        raise DuplicateError
    row = insert_middle_category(user_id, major_category_id, trimmed)
    write("INF", f"中項目登録成功 user_id={user_id} middle_category_id={row.id}")
    return _middle_body(row)


def rename_middle(user_id: int, middle_category_id: int, name: str) -> dict[str, object]:
    write("INF", f"中項目名称変更要求 user_id={user_id} middle_category_id={middle_category_id}")
    existing = get_middle_category(user_id, middle_category_id)
    if existing is None:
        write("WRN", f"中項目名称変更失敗 user_id={user_id} middle_category_id={middle_category_id} 理由=対象なし")
        raise NotFoundError
    trimmed = _validate_name(name)
    if middle_category_name_exists(existing.major_category_id, trimmed, exclude_id=middle_category_id):
        write(
            "WRN",
            f"中項目名称変更失敗 user_id={user_id} middle_category_id={middle_category_id} 理由=重複",
        )
        raise DuplicateError
    update_middle_category_name(middle_category_id, user_id, trimmed)
    updated = get_middle_category(user_id, middle_category_id)
    assert updated is not None
    write("INF", f"中項目名称変更成功 user_id={user_id} middle_category_id={middle_category_id}")
    return _middle_body(updated)


def remove_middle(user_id: int, middle_category_id: int) -> None:
    write("INF", f"中項目削除要求 user_id={user_id} middle_category_id={middle_category_id}")
    existing = get_middle_category(user_id, middle_category_id)
    if existing is None:
        write("WRN", f"中項目削除失敗 user_id={user_id} middle_category_id={middle_category_id} 理由=対象なし")
        raise NotFoundError
    cascade_delete_middle_category(middle_category_id, user_id)
    write("INF", f"中項目削除成功 user_id={user_id} middle_category_id={middle_category_id}")
