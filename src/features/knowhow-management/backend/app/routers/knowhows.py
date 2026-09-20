from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.deps import AuthContext, get_current_user
from app.errors import InvalidInputError, NotFoundError
from app.services import knowhow_service

router = APIRouter(prefix="/knowhows")


class KnowhowBody(BaseModel):
    title: str
    keywords: str | None = None
    content: str
    middle_category_id: int | None = None


class SwapBody(BaseModel):
    knowhow_id_a: int
    knowhow_id_b: int


@router.get("/search")
def search_knowhows(
    keyword: list[str] = Query(default=[]),
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, list[dict[str, object]]]:
    try:
        return {"items": knowhow_service.search(auth.user.id, keyword)}
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None


@router.get("/{knowhow_id}")
def get_knowhow(
    knowhow_id: int,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return knowhow_service.get_for_user(auth.user.id, knowhow_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.post("", status_code=201)
def create_knowhow(
    body: KnowhowBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return knowhow_service.create_knowhow(
            auth.user.id, body.title, body.keywords, body.content, body.middle_category_id
        )
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.patch("/{knowhow_id}")
def update_knowhow(
    knowhow_id: int,
    body: KnowhowBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return knowhow_service.change_knowhow(
            auth.user.id, knowhow_id, body.title, body.keywords, body.content, body.middle_category_id
        )
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.delete("/{knowhow_id}", status_code=204)
def delete_knowhow(
    knowhow_id: int,
    auth: AuthContext = Depends(get_current_user),
) -> None:
    try:
        knowhow_service.remove_knowhow(auth.user.id, knowhow_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.post("/swap-display-order", status_code=204)
def swap_display_order(
    body: SwapBody,
    auth: AuthContext = Depends(get_current_user),
) -> None:
    try:
        knowhow_service.swap_display_order(auth.user.id, body.knowhow_id_a, body.knowhow_id_b)
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
