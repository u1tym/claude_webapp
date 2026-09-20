from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.common import Name100
from app.deps import AuthContext, get_current_user
from app.services import genre_service

router = APIRouter(tags=["genres"])


class GenreCreate(BaseModel):
    name: Name100
    sort_order: Annotated[int, Field(ge=0)] = 0


@router.get("/genres")
def list_genres(auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return genre_service.list_genres(auth.user.id)


@router.post("/genres", status_code=201)
def create_genre(body: GenreCreate, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return genre_service.create_genre(auth.user.id, body.name, body.sort_order)
