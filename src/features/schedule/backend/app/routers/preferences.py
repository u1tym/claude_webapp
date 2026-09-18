from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.deps import AuthContext, get_current_user
from app.errors import InvalidInputError
from app.services import preference_service

router = APIRouter(prefix="/preferences")


class PreferenceBody(BaseModel):
    week_starts_on: str
    show_deleted: bool
    hidden_category_ids: list[int]


@router.get("")
def get_preferences(auth: AuthContext = Depends(get_current_user)) -> dict[str, object]:
    return preference_service.get_for_user(auth.user.id)


@router.put("")
def put_preferences(
    body: PreferenceBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return preference_service.save_for_user(
            auth.user.id,
            body.week_starts_on,
            body.show_deleted,
            body.hidden_category_ids,
        )
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
