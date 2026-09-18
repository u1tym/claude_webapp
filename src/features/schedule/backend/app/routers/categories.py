from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.deps import AuthContext, get_current_user
from app.errors import DuplicateError, InvalidInputError, NotFoundError
from app.services import category_service

router = APIRouter(prefix="/categories")


class CategoryBody(BaseModel):
    name: str
    color: str


def _parse_include_deleted(raw: str | None) -> bool:
    if raw is None:
        return False
    lowered = raw.strip().lower()
    if lowered in ("true", "1"):
        return True
    if lowered in ("false", "0"):
        return False
    raise HTTPException(status_code=400, detail="入力が不正です")


@router.get("")
def list_categories(
    include_deleted: str | None = Query(default=None),
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, list[dict[str, object]]]:
    try:
        flag = _parse_include_deleted(include_deleted)
        items = category_service.list_for_user(auth.user.id, flag)
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    return {"items": items}


@router.post("", status_code=201)
def create_category(
    body: CategoryBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return category_service.add_category(auth.user.id, body.name, body.color)
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except DuplicateError:
        raise HTTPException(status_code=409, detail="保存できませんでした") from None


@router.patch("/{category_id}")
def patch_category(
    category_id: int,
    body: CategoryBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return category_service.change_category(auth.user.id, category_id, body.name, body.color)
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
    except DuplicateError:
        raise HTTPException(status_code=409, detail="保存できませんでした") from None


@router.delete("/{category_id}", status_code=204)
def delete_category(
    category_id: int,
    auth: AuthContext = Depends(get_current_user),
) -> None:
    try:
        category_service.remove_category(auth.user.id, category_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
