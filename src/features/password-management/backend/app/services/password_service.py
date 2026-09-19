from __future__ import annotations

from app.errors import DuplicateError, InvalidInputError, NotFoundError
from app.logger import safe_text, write
from app.repos import (
    EntryRow,
    get_entry,
    insert_entry,
    list_entries,
    logical_delete_entry,
    search_entries,
    title_exists,
    update_entry,
)


def _validate_text(title: str, userword: str, psword: str) -> tuple[str, str]:
    trimmed_title = title.strip()
    if trimmed_title == "":
        raise InvalidInputError("タイトルが空")
    trimmed_userword = userword.strip()
    if trimmed_userword == "":
        raise InvalidInputError("ユーザ名が空")
    if psword == "":
        raise InvalidInputError("パスワードが空")
    return trimmed_title, trimmed_userword


def _summary(row: EntryRow) -> dict[str, object]:
    return {
        "id": row.id,
        "title": row.title,
        "userword": row.userword,
        "site": row.site,
        "memo": row.memo,
    }


def _full(row: EntryRow) -> dict[str, object]:
    return {
        "id": row.id,
        "title": row.title,
        "userword": row.userword,
        "psword": row.psword,
        "site": row.site,
        "memo": row.memo,
    }


def list_for_user(user_id: int, keyword: str | None) -> list[dict[str, object]]:
    trimmed_keyword = (keyword or "").strip()
    if trimmed_keyword == "":
        write("INF", f"パスワードエントリ一覧要求 user_id={user_id}")
        rows = list_entries(user_id)
    else:
        write("INF", f"パスワードエントリ検索要求 user_id={user_id} keyword={safe_text(trimmed_keyword)}")
        rows = search_entries(user_id, trimmed_keyword)
    items = [_summary(row) for row in rows]
    write("INF", f"パスワードエントリ一覧成功 user_id={user_id} count={len(items)}")
    return items


def get_for_user(user_id: int, entry_id: int) -> dict[str, object]:
    write("INF", f"パスワードエントリ取得要求 user_id={user_id} entry_id={entry_id}")
    row = get_entry(user_id, entry_id)
    if row is None:
        write("WRN", f"パスワードエントリ取得失敗 user_id={user_id} entry_id={entry_id} 理由=対象なし")
        raise NotFoundError
    write("INF", f"パスワードエントリ取得成功 user_id={user_id} entry_id={entry_id}")
    return _full(row)


def create_entry(
    user_id: int,
    title: str,
    userword: str,
    psword: str,
    site: str | None,
    memo: str | None,
) -> dict[str, object]:
    write("INF", f"パスワードエントリ登録要求 user_id={user_id} title={safe_text(title)}")
    trimmed_title, trimmed_userword = _validate_text(title, userword, psword)
    if title_exists(user_id, trimmed_title):
        write("WRN", f"パスワードエントリ登録失敗 user_id={user_id} title={safe_text(trimmed_title)} 理由=重複")
        raise DuplicateError
    row = insert_entry(
        user_id,
        trimmed_title,
        trimmed_userword,
        psword,
        (site.strip() or None) if site is not None else None,
        (memo.strip() or None) if memo is not None else None,
    )
    write("INF", f"パスワードエントリ登録成功 user_id={user_id} entry_id={row.id}")
    return _full(row)


def change_entry(
    user_id: int,
    entry_id: int,
    title: str,
    userword: str,
    psword: str,
    site: str | None,
    memo: str | None,
) -> dict[str, object]:
    write("INF", f"パスワードエントリ更新要求 user_id={user_id} entry_id={entry_id}")
    existing = get_entry(user_id, entry_id)
    if existing is None:
        write("WRN", f"パスワードエントリ更新失敗 user_id={user_id} entry_id={entry_id} 理由=対象なし")
        raise NotFoundError
    trimmed_title, trimmed_userword = _validate_text(title, userword, psword)
    if title_exists(user_id, trimmed_title, exclude_id=entry_id):
        write(
            "WRN",
            f"パスワードエントリ更新失敗 user_id={user_id} entry_id={entry_id} 理由=重複",
        )
        raise DuplicateError
    update_entry(
        entry_id,
        user_id,
        trimmed_title,
        trimmed_userword,
        psword,
        (site.strip() or None) if site is not None else None,
        (memo.strip() or None) if memo is not None else None,
    )
    updated = get_entry(user_id, entry_id)
    assert updated is not None
    write("INF", f"パスワードエントリ更新成功 user_id={user_id} entry_id={entry_id}")
    return _full(updated)


def remove_entry(user_id: int, entry_id: int) -> None:
    write("INF", f"パスワードエントリ削除要求 user_id={user_id} entry_id={entry_id}")
    existing = get_entry(user_id, entry_id)
    if existing is None:
        write("WRN", f"パスワードエントリ削除失敗 user_id={user_id} entry_id={entry_id} 理由=対象なし")
        raise NotFoundError
    logical_delete_entry(entry_id, user_id)
    write("INF", f"パスワードエントリ削除成功 user_id={user_id} entry_id={entry_id}")
