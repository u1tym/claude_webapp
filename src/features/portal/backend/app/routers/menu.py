from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.deps import AuthContext, get_current_user
from app.logger import safe_text, write
from app.security import to_data_url
from app.services.menu_service import list_allowed_menu_items

router = APIRouter()


class NavLogBody(BaseModel):
    id: str = ""
    title: str = ""
    from_db: str = ""
    destination: str = ""
    error: str = ""


@router.get("/menu")
def get_menu(auth: AuthContext = Depends(get_current_user)) -> dict[str, list[dict[str, str]]]:
    username = safe_text(auth.user.username)
    write("INF", f"メニュー取得要求 username={username}")
    items = list_allowed_menu_items(auth.user.id)
    write("INF", f"メニュー取得成功 username={username} count={len(items)}")
    for item in items:
        write(
            "INF",
            f"メニュー項目 id={safe_text(item.id)} title={safe_text(item.title)} url={safe_text(item.url)}",
        )
    return {
        "items": [
            {
                "id": item.id,
                "title": item.title,
                "url": item.url,
                "icon": to_data_url(item.icon_media_type, item.icon),
            }
            for item in items
        ]
    }


@router.post("/menu/nav-log", status_code=204)
def log_menu_navigation(
    body: NavLogBody,
    auth: AuthContext = Depends(get_current_user),
) -> None:
    write(
        "INF",
        "メニュー遷移"
        f" username={safe_text(auth.user.username)}"
        f" id={safe_text(body.id)}"
        f" title={safe_text(body.title)}"
        f" from_db={safe_text(body.from_db)}"
        f" destination={safe_text(body.destination)}"
        f" error={safe_text(body.error)}",
    )
