from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.common import Page, Title500, page_params
from app.deps import AuthContext, get_current_user
from app.services import series_service

router = APIRouter(tags=["series"])


class SeriesCreate(BaseModel):
    title: Title500
    description: str | None = None


@router.get("/series")
def list_series(
    paging: Page = Depends(page_params),
    q: str | None = Query(None),
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    return series_service.list_series(auth.user.id, paging, q)


@router.post("/series", status_code=201)
def create_series(body: SeriesCreate, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return series_service.create_series(auth.user.id, body.title, body.description)


@router.get("/series/{series_id}")
def get_series(series_id: int, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return series_service.get_series_detail(auth.user.id, series_id)
