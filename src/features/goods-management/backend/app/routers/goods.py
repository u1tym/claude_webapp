from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.deps import AuthContext, get_current_user
from app.errors import InvalidInputError, NotFoundError
from app.services import goods_service

router = APIRouter(prefix="/goods")


class GoodsBody(BaseModel):
    media_id: int
    artist_id: int
    title: str
    release_date: date | None = None
    memo: str | None = None
    is_owned: bool = False
    code_number: str | None = None


class GoodsImageBody(BaseModel):
    image_type: str
    image_data: str


@router.get("")
def list_goods(
    person_id: int = Query(...),
    artist_id: int | None = Query(default=None),
    media_id: int | None = Query(default=None),
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, list[dict[str, object]]]:
    try:
        items = goods_service.list_goods_view(auth.user.id, person_id, artist_id, media_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
    return {"items": items}


@router.get("/{goods_id}")
def get_goods(
    goods_id: int,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return goods_service.get_goods_view(auth.user.id, goods_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.post("", status_code=201)
def create_goods(
    body: GoodsBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return goods_service.create_goods(
            auth.user.id,
            body.media_id,
            body.artist_id,
            body.title,
            body.release_date,
            body.memo,
            body.is_owned,
            body.code_number,
        )
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.patch("/{goods_id}")
def update_goods(
    goods_id: int,
    body: GoodsBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return goods_service.update_goods_view(
            auth.user.id,
            goods_id,
            body.media_id,
            body.artist_id,
            body.title,
            body.release_date,
            body.memo,
            body.is_owned,
            body.code_number,
        )
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.delete("/{goods_id}", status_code=204)
def delete_goods(
    goods_id: int,
    auth: AuthContext = Depends(get_current_user),
) -> None:
    try:
        goods_service.remove_goods(auth.user.id, goods_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.post("/{goods_id}/images", status_code=201)
def add_goods_image(
    goods_id: int,
    body: GoodsImageBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return goods_service.add_image(auth.user.id, goods_id, body.image_type, body.image_data)
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.delete("/{goods_id}/images/{image_id}", status_code=204)
def delete_goods_image(
    goods_id: int,
    image_id: int,
    auth: AuthContext = Depends(get_current_user),
) -> None:
    try:
        goods_service.remove_image(auth.user.id, goods_id, image_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
