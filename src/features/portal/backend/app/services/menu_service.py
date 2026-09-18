from __future__ import annotations

from app.repos import MenuItemRow, list_menu_items
from app.services.access_service import is_feature_allowed


def list_allowed_menu_items(user_id: int) -> list[MenuItemRow]:
    items = list_menu_items(user_id)
    return [item for item in items if is_feature_allowed(user_id, item.id)]
