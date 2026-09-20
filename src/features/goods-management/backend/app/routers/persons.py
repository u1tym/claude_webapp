from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.deps import AuthContext, get_current_user
from app.errors import InvalidInputError, NotFoundError, ReferencedError
from app.services import goods_service, master_service

router = APIRouter(prefix="/persons")


class PersonBody(BaseModel):
    name: str


@router.get("")
def list_persons(
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, list[dict[str, object]]]:
    return {"items": master_service.list_persons_view(auth.user.id)}


@router.post("", status_code=201)
def create_person(
    body: PersonBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return master_service.create_person(auth.user.id, body.name)
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None


@router.patch("/{person_id}")
def rename_person(
    person_id: int,
    body: PersonBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return master_service.rename_person(auth.user.id, person_id, body.name)
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.delete("/{person_id}", status_code=204)
def delete_person(
    person_id: int,
    auth: AuthContext = Depends(get_current_user),
) -> None:
    try:
        master_service.remove_person(auth.user.id, person_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
    except ReferencedError:
        raise HTTPException(
            status_code=409, detail="他のデータから参照されているため削除できません"
        ) from None


@router.get("/{person_id}/related-artists")
def get_related_artists(
    person_id: int,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, list[dict[str, object]]]:
    try:
        return {"items": goods_service.related_artists(auth.user.id, person_id)}
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.get("/{person_id}/related-media")
def get_related_media(
    person_id: int,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, list[dict[str, object]]]:
    try:
        return {"items": goods_service.related_media(auth.user.id, person_id)}
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
