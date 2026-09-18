from __future__ import annotations

from psycopg2 import errors

from app.config import FEATURE_ID
from app.logger import safe_text, write
from app.repos import (
    FeatureRow,
    get_feature,
    insert_feature,
    list_active_features,
    logical_delete_feature,
    update_feature,
)
from app.security import from_data_url


class NotFoundError(Exception):
    pass


class DuplicateError(Exception):
    pass


class ForbiddenOpError(Exception):
    pass


class InvalidIconError(Exception):
    pass


def list_features() -> list[FeatureRow]:
    write("INF", "機能一覧要求")
    items = list_active_features()
    write("INF", f"機能一覧成功 count={len(items)}")
    return items


def add_feature(feature_id: str, title: str, url: str, icon: str) -> FeatureRow:
    logged = safe_text(feature_id)
    write("INF", f"機能追加要求 id={logged} title={safe_text(title)}")
    parsed = from_data_url(icon)
    if parsed is None:
        write("WRN", f"機能追加失敗 id={logged} 理由=入力不正")
        raise InvalidIconError
    media_type, raw = parsed
    if get_feature(feature_id) is not None:
        write("WRN", f"機能追加失敗 id={logged} 理由=重複")
        raise DuplicateError
    try:
        row = insert_feature(feature_id, title, url, raw, media_type)
    except errors.UniqueViolation:
        write("WRN", f"機能追加失敗 id={logged} 理由=重複")
        raise DuplicateError from None
    write("INF", f"機能追加成功 id={logged}")
    return row


def change_feature(feature_id: str, title: str, url: str, icon: str | None) -> FeatureRow:
    logged = safe_text(feature_id)
    write("INF", f"機能更新要求 id={logged} title={safe_text(title)}")
    current = get_feature(feature_id)
    if current is None or current.is_deleted:
        write("WRN", f"機能更新失敗 id={logged} 理由=対象なし")
        raise NotFoundError
    media: str | None = None
    raw: bytes | None = None
    if icon:
        parsed = from_data_url(icon)
        if parsed is None:
            write("WRN", f"機能更新失敗 id={logged} 理由=入力不正")
            raise InvalidIconError
        media, raw = parsed
    update_feature(feature_id, title, url, raw, media)
    updated = get_feature(feature_id)
    assert updated is not None
    write("INF", f"機能更新成功 id={logged}")
    return updated


def remove_feature(feature_id: str) -> None:
    logged = safe_text(feature_id)
    write("INF", f"機能削除要求 id={logged}")
    if feature_id == FEATURE_ID:
        write("WRN", f"機能削除失敗 id={logged} 理由=本機能")
        raise ForbiddenOpError
    current = get_feature(feature_id)
    if current is None or current.is_deleted:
        write("WRN", f"機能削除失敗 id={logged} 理由=対象なし")
        raise NotFoundError
    logical_delete_feature(feature_id)
    write("INF", f"機能削除成功 id={logged}")
