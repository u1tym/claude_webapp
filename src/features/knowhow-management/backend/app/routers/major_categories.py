from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.deps import AuthContext, get_current_user
from app.errors import DuplicateError, InvalidInputError, NotFoundError
from app.services import category_service

router = APIRouter(prefix="/major-categories")


class MajorCategoryBody(BaseModel):
    name: str


@router.get("")
def list_major_categories(
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, list[dict[str, object]]]:
    return {"items": category_service.list_majors(auth.user.id)}


@router.post("", status_code=201)
def create_major_category(
    body: MajorCategoryBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return category_service.create_major(auth.user.id, body.name)
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except DuplicateError:
        raise HTTPException(status_code=409, detail="保存できませんでした") from None


@router.patch("/{major_category_id}")
def rename_major_category(
    major_category_id: int,
    body: MajorCategoryBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return category_service.rename_major(auth.user.id, major_category_id, body.name)
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
    except DuplicateError:
        raise HTTPException(status_code=409, detail="保存できませんでした") from None


@router.delete("/{major_category_id}", status_code=204)
def delete_major_category(
    major_category_id: int,
    auth: AuthContext = Depends(get_current_user),
) -> None:
    try:
        category_service.remove_major(auth.user.id, major_category_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.get("/{major_category_id}/middle-categories")
def list_middle_categories(
    major_category_id: int,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, list[dict[str, object]]]:
    try:
        return {"items": category_service.list_middles(auth.user.id, major_category_id)}
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.post("/{major_category_id}/middle-categories", status_code=201)
def create_middle_category(
    major_category_id: int,
    body: MajorCategoryBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return category_service.create_middle(auth.user.id, major_category_id, body.name)
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
    except DuplicateError:
        raise HTTPException(status_code=409, detail="保存できませんでした") from None
