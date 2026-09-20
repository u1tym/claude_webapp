from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.deps import AuthContext, get_current_user
from app.errors import InvalidInputError, NotFoundError, ReferencedError
from app.services import master_service

router = APIRouter(prefix="/artists")


class ArtistBody(BaseModel):
    name: str
    person_ids: list[int] = Field(default_factory=list)


@router.get("")
def list_artists(
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, list[dict[str, object]]]:
    return {"items": master_service.list_artists_view(auth.user.id)}


@router.get("/{artist_id}")
def get_artist(
    artist_id: int,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return master_service.get_artist_view(auth.user.id, artist_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.post("", status_code=201)
def create_artist(
    body: ArtistBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return master_service.create_artist(auth.user.id, body.name, body.person_ids)
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.patch("/{artist_id}")
def update_artist(
    artist_id: int,
    body: ArtistBody,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return master_service.update_artist(auth.user.id, artist_id, body.name, body.person_ids)
    except InvalidInputError:
        raise HTTPException(status_code=400, detail="入力が不正です") from None
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None


@router.delete("/{artist_id}", status_code=204)
def delete_artist(
    artist_id: int,
    auth: AuthContext = Depends(get_current_user),
) -> None:
    try:
        master_service.remove_artist(auth.user.id, artist_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="対象がありません") from None
    except ReferencedError:
        raise HTTPException(
            status_code=409, detail="他のデータから参照されているため削除できません"
        ) from None
