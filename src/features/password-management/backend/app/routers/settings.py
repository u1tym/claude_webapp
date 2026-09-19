from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.logger import write
from app.repos import get_setting
from app.security import to_data_url

router = APIRouter()


@router.get("/settings")
def get_settings() -> dict[str, str]:
    write("INF", "設定取得要求")
    login = get_setting("login_url")
    menu = get_setting("menu_url")
    icon_system = get_setting("icon_system")
    icon_back = get_setting("icon_back")
    if (
        login is None
        or login.value_text is None
        or menu is None
        or menu.value_text is None
        or icon_system is None
        or icon_system.value_bytes is None
        or icon_system.value_media_type is None
        or icon_back is None
        or icon_back.value_bytes is None
        or icon_back.value_media_type is None
    ):
        write("ERR", "設定取得失敗 理由=必須キー欠け")
        raise HTTPException(status_code=500, detail="サーバエラーです")
    write("INF", "設定取得成功")
    return {
        "login_url": login.value_text,
        "menu_url": menu.value_text,
        "icon_system": to_data_url(icon_system.value_media_type, icon_system.value_bytes),
        "icon_back": to_data_url(icon_back.value_media_type, icon_back.value_bytes),
    }
