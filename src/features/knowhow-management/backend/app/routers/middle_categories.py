from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.deps import AuthContext, get_current_user
from app.errors import DuplicateError, InvalidInputError, NotFoundError
from app.services import category_service, knowhow_service

router = APIRouter(prefix="/middle-categories")


class MiddleCategoryBody(BaseModel):
    name: str


@router.get("/{middle_category_id}/knowhows")
def list_knowhows(
    middle_category_id: int,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, list[dict[str, object]]]:
    try:
        return {"items": knowhow_service.list_for_middle(auth.user.id, middle_category_id)}
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.patch("/{middle_category_id}")
def rename_middle_category(
    middle_category_id: int,
    body: MiddleCategoryBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return category_service.rename_middle(auth.user.id, middle_category_id, body.name)
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
    except DuplicateError:
        raise HTTPException(status_code=409, detail="保存できませんでした") from None


@router.delete("/{middle_category_id}", status_code=204)
def delete_middle_category(
    middle_category_id: int,
    auth: AuthContext = Depends(get_current_user),
) -> None:
    try:
        category_service.remove_middle(auth.user.id, middle_category_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
