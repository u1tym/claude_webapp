from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import AuthContext, get_current_user
from app.errors import InvalidInputError
from app.services import holiday_service
from app.services.category_service import parse_date

router = APIRouter(prefix="/holidays")


@router.get("")
def list_holidays(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, list[dict[str, str]]]:
    if start_date is None or end_date is None:
        raise HTTPException(status_code=400, detail="入力が不正です")
    try:
        start = parse_date(start_date)
        end = parse_date(end_date)
        items = holiday_service.list_national_holidays(start, end)
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    return {"items": items}
