from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.deps import AuthContext, get_current_user
from app.errors import InvalidInputError, NotFoundError, ReferencedError
from app.services import master_service

router = APIRouter(prefix="/media")


class MediaBody(BaseModel):
    name: str


@router.get("")
def list_media(
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, list[dict[str, object]]]:
    return {"items": master_service.list_media_view(auth.user.id)}


@router.post("", status_code=201)
def create_media(
    body: MediaBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return master_service.create_media(auth.user.id, body.name)
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None


@router.patch("/{media_id}")
def rename_media(
    media_id: int,
    body: MediaBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return master_service.rename_media(auth.user.id, media_id, body.name)
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.delete("/{media_id}", status_code=204)
def delete_media(
    media_id: int,
    auth: AuthContext = Depends(get_current_user),
) -> None:
    try:
        master_service.remove_media(auth.user.id, media_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
    except ReferencedError:
        raise HTTPException(
            status_code=409, detail="他のデータから参照されているため削除できません"
        ) from None
