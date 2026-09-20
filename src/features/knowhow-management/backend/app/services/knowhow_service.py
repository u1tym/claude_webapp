from __future__ import annotations

from app.errors import InvalidInputError, NotFoundError
from app.logger import safe_text, write
from app.repos import (
    KnowhowRow,
    get_knowhow,
    get_middle_category,
    insert_knowhow,
    list_knowhows_by_middle,
    logical_delete_knowhow,
    next_knowhow_display_order,
    search_knowhows,
    set_knowhow_display_order,
    update_knowhow,
)


def _validate_text(title: str, content: str) -> tuple[str, str]:
    trimmed_title = title.strip()
    if trimmed_title == "":
        raise InvalidInputError("タイトルが空")
    trimmed_content = content.strip()
    if trimmed_content == "":
        raise InvalidInputError("本文が空")
    return trimmed_title, trimmed_content


def _summary(row: KnowhowRow) -> dict[str, object]:
    return {
        "id": row.id,
        "title": row.title,
        "keywords": row.keywords,
        "middle_category_id": row.middle_category_id,
        "display_order": row.display_order,
    }


def _detail(row: KnowhowRow) -> dict[str, object]:
    return {
        "id": row.id,
        "title": row.title,
        "keywords": row.keywords,
        "content": row.content,
        "middle_category_id": row.middle_category_id,
        "display_order": row.display_order,
    }


def _check_middle_category(user_id: int, middle_category_id: int | None) -> None:
    if middle_category_id is None:
        return
    if get_middle_category(user_id, middle_category_id) is None:
        raise NotFoundError


def list_for_middle(user_id: int, middle_category_id: int) -> list[dict[str, object]]:
    write("INF", f"ノウハウ一覧要求 user_id={user_id} middle_category_id={middle_category_id}")
    if get_middle_category(user_id, middle_category_id) is None:
        write("WRN", f"ノウハウ一覧失敗 user_id={user_id} middle_category_id={middle_category_id} 理由=対象なし")
        raise NotFoundError
    items = [_summary(row) for row in list_knowhows_by_middle(user_id, middle_category_id)]
    write("INF", f"ノウハウ一覧成功 user_id={user_id} middle_category_id={middle_category_id} count={len(items)}")
    return items


def get_for_user(user_id: int, knowhow_id: int) -> dict[str, object]:
    write("INF", f"ノウハウ取得要求 user_id={user_id} knowhow_id={knowhow_id}")
    row = get_knowhow(user_id, knowhow_id)
    if row is None:
        write("WRN", f"ノウハウ取得失敗 user_id={user_id} knowhow_id={knowhow_id} 理由=対象なし")
        raise NotFoundError
    write("INF", f"ノウハウ取得成功 user_id={user_id} knowhow_id={knowhow_id}")
    return _detail(row)


def create_knowhow(
    user_id: int,
    title: str,
    keywords: str | None,
    content: str,
    middle_category_id: int | None,
) -> dict[str, object]:
    write(
        "INF",
        f"ノウハウ登録要求 user_id={user_id} title={safe_text(title)} middle_category_id={middle_category_id}",
    )
    trimmed_title, trimmed_content = _validate_text(title, content)
    try:
        _check_middle_category(user_id, middle_category_id)
    except NotFoundError:
        write("WRN", f"ノウハウ登録失敗 user_id={user_id} middle_category_id={middle_category_id} 理由=対象なし")
        raise
    display_order = next_knowhow_display_order(user_id, middle_category_id)
    row = insert_knowhow(
        user_id,
        middle_category_id,
        trimmed_title,
        (keywords.strip() or None) if keywords is not None else None,
        trimmed_content,
        display_order,
    )
    write("INF", f"ノウハウ登録成功 user_id={user_id} knowhow_id={row.id}")
    return _detail(row)


def change_knowhow(
    user_id: int,
    knowhow_id: int,
    title: str,
    keywords: str | None,
    content: str,
    middle_category_id: int | None,
) -> dict[str, object]:
    write("INF", f"ノウハウ更新要求 user_id={user_id} knowhow_id={knowhow_id}")
    existing = get_knowhow(user_id, knowhow_id)
    if existing is None:
        write("WRN", f"ノウハウ更新失敗 user_id={user_id} knowhow_id={knowhow_id} 理由=対象なし")
        raise NotFoundError
    trimmed_title, trimmed_content = _validate_text(title, content)
    try:
        _check_middle_category(user_id, middle_category_id)
    except NotFoundError:
        write("WRN", f"ノウハウ更新失敗 user_id={user_id} knowhow_id={knowhow_id} 理由=所属先なし")
        raise
    if existing.middle_category_id != middle_category_id:
        display_order = next_knowhow_display_order(user_id, middle_category_id)
    else:
        display_order = existing.display_order
    update_knowhow(
        knowhow_id,
        user_id,
        middle_category_id,
        trimmed_title,
        (keywords.strip() or None) if keywords is not None else None,
        trimmed_content,
        display_order,
    )
    updated = get_knowhow(user_id, knowhow_id)
    assert updated is not None
    write("INF", f"ノウハウ更新成功 user_id={user_id} knowhow_id={knowhow_id}")
    return _detail(updated)


def remove_knowhow(user_id: int, knowhow_id: int) -> None:
    write("INF", f"ノウハウ削除要求 user_id={user_id} knowhow_id={knowhow_id}")
    existing = get_knowhow(user_id, knowhow_id)
    if existing is None:
        write("WRN", f"ノウハウ削除失敗 user_id={user_id} knowhow_id={knowhow_id} 理由=対象なし")
        raise NotFoundError
    logical_delete_knowhow(knowhow_id, user_id)
    write("INF", f"ノウハウ削除成功 user_id={user_id} knowhow_id={knowhow_id}")


def swap_display_order(user_id: int, knowhow_id_a: int, knowhow_id_b: int) -> None:
    write("INF", f"ノウハウ並び替え要求 user_id={user_id} a={knowhow_id_a} b={knowhow_id_b}")
    row_a = get_knowhow(user_id, knowhow_id_a)
    row_b = get_knowhow(user_id, knowhow_id_b)
    if row_a is None or row_b is None:
        write("WRN", f"ノウハウ並び替え失敗 user_id={user_id} a={knowhow_id_a} b={knowhow_id_b} 理由=対象なし")
        raise NotFoundError
    if row_a.middle_category_id != row_b.middle_category_id:
        write(
            "WRN",
            f"ノウハウ並び替え失敗 user_id={user_id} a={knowhow_id_a} b={knowhow_id_b} 理由=所属先不一致",
        )
        raise InvalidInputError("所属先が一致しない")
    set_knowhow_display_order(knowhow_id_a, user_id, row_b.display_order)
    set_knowhow_display_order(knowhow_id_b, user_id, row_a.display_order)
    write("INF", f"ノウハウ並び替え成功 user_id={user_id} a={knowhow_id_a} b={knowhow_id_b}")


def search(user_id: int, keywords: list[str]) -> list[dict[str, object]]:
    trimmed = [k.strip() for k in keywords if k.strip() != ""]
    if not trimmed:
        raise InvalidInputError("キーワードが無い")
    write("INF", f"ノウハウ検索要求 user_id={user_id} keywords={safe_text(','.join(trimmed))}")
    rows = search_knowhows(user_id, trimmed)
    items = [
        {
            "knowhow_id": row.knowhow_id,
            "title": row.title,
            "display_order": row.display_order,
            "major_category_id": row.major_category_id,
            "major_category_name": row.major_category_name,
            "middle_category_id": row.middle_category_id,
            "middle_category_name": row.middle_category_name,
        }
        for row in rows
    ]
    write("INF", f"ノウハウ検索成功 user_id={user_id} count={len(items)}")
    return items
