from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.deps import AuthContext, get_current_user
from app.errors import DuplicateError, InvalidInputError, NotFoundError
from app.services import user_holiday_service
from app.services.category_service import parse_date

router = APIRouter(prefix="/user-holidays")


class UserHolidayBody(BaseModel):
    holiday_date: str
    name: str


@router.get("")
def list_user_holidays(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, list[dict[str, object]]]:
    try:
        start = parse_date(start_date) if start_date is not None else None
        end = parse_date(end_date) if end_date is not None else None
        items = user_holiday_service.list_for_user(auth.user.id, start, end)
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    return {"items": items}


@router.post("", status_code=201)
def create_user_holiday(
    body: UserHolidayBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        holiday_date = parse_date(body.holiday_date)
        return user_holiday_service.add_user_holiday(auth.user.id, holiday_date, body.name)
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except DuplicateError:
        raise HTTPException(status_code=409, detail="保存できませんでした") from None


@router.patch("/{user_holiday_id}")
def patch_user_holiday(
    user_holiday_id: int,
    body: UserHolidayBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        holiday_date = parse_date(body.holiday_date)
        return user_holiday_service.change_user_holiday(
            auth.user.id,
            user_holiday_id,
            holiday_date,
            body.name,
        )
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
    except DuplicateError:
        raise HTTPException(status_code=409, detail="保存できませんでした") from None


@router.delete("/{user_holiday_id}", status_code=204)
def delete_user_holiday(
    user_holiday_id: int,
    auth: AuthContext = Depends(get_current_user),
) -> None:
    try:
        user_holiday_service.remove_user_holiday(auth.user.id, user_holiday_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
