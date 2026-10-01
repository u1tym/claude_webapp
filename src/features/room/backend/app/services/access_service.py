from __future__ import annotations

from app.repos import assignment_exists, get_feature, get_user_by_id


def is_feature_allowed(user_id: int, feature_id: str) -> bool:
    """ユーザと機能が未削除で、機能がユーザに割り当てられているかを返す。"""
    user = get_user_by_id(user_id)
    if user is None or user.is_deleted:
        return False
    feature = get_feature(feature_id)
    if feature is None or feature.is_deleted:
        return False
    return assignment_exists(user_id, feature_id)
