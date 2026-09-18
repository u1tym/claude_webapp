from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.repos import get_setting
from app.security import to_data_url

router = APIRouter()

REQUIRED_TEXT = ("login_url", "menu_url")
REQUIRED_ICON = ("icon_system", "icon_settings", "icon_back")


@router.get("/settings")
def get_settings() -> dict[str, str]:
    result: dict[str, str] = {}
    for key in REQUIRED_TEXT:
        row = get_setting(key)
        if row is None or row.value_text is None:
            raise HTTPException(status_code=500, detail="サーバエラーです")
        result[key] = row.value_text
    for key in REQUIRED_ICON:
        row = get_setting(key)
        if row is None or row.value_bytes is None or row.value_media_type is None:
            raise HTTPException(status_code=500, detail="サーバエラーです")
        result[key] = to_data_url(row.value_media_type, row.value_bytes)
    return result
