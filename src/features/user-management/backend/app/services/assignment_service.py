from __future__ import annotations

from psycopg2 import errors

from app.config import FEATURE_ID
from app.logger import safe_text, write
from app.repos import (
    AssignmentRow,
    assignment_exists,
    delete_assignment,
    get_feature,
    get_user_by_id,
    insert_assignment,
    list_active_assignments,
)


class NotFoundError(Exception):
    pass


class DuplicateError(Exception):
    pass


class ForbiddenOpError(Exception):
    pass


def list_assignments() -> list[AssignmentRow]:
    write("INF", "割当一覧要求")
    items = list_active_assignments()
    write("INF", f"割当一覧成功 count={len(items)}")
    return items


def add_assignment(user_id: int, feature_id: str, display_order: int) -> AssignmentRow:
    logged = safe_text(feature_id)
    write("INF", f"割当追加要求 user_id={user_id} feature_id={logged} order={display_order}")
    user = get_user_by_id(user_id)
    if user is None or user.is_deleted:
        write("WRN", f"割当追加失敗 user_id={user_id} 理由=対象なし")
        raise NotFoundError
    feature = get_feature(feature_id)
    if feature is None or feature.is_deleted:
        write("WRN", f"割当追加失敗 feature_id={logged} 理由=対象なし")
        raise NotFoundError
    if assignment_exists(user_id, feature_id):
        write("WRN", f"割当追加失敗 user_id={user_id} feature_id={logged} 理由=重複")
        raise DuplicateError
    try:
        insert_assignment(user_id, feature_id, display_order)
    except errors.UniqueViolation:
        write("WRN", f"割当追加失敗 user_id={user_id} feature_id={logged} 理由=重複")
        raise DuplicateError from None
    write("INF", f"割当追加成功 user_id={user_id} feature_id={logged}")
    return AssignmentRow(
        user_id=user.id,
        username=user.username,
        feature_id=feature.id,
        feature_title=feature.title,
        display_order=display_order,
    )


def remove_assignment(user_id: int, feature_id: str, actor_id: int) -> None:
    logged = safe_text(feature_id)
    write("INF", f"割当解除要求 user_id={user_id} feature_id={logged} actor_id={actor_id}")
    if user_id == actor_id and feature_id == FEATURE_ID:
        write("WRN", f"割当解除失敗 user_id={user_id} feature_id={logged} 理由=自己からの本機能割当解除")
        raise ForbiddenOpError
    if not assignment_exists(user_id, feature_id):
        write("WRN", f"割当解除失敗 user_id={user_id} feature_id={logged} 理由=対象なし")
        raise NotFoundError
    delete_assignment(user_id, feature_id)
    write("INF", f"割当解除成功 user_id={user_id} feature_id={logged}")
