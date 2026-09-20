from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.common import Page, Text500, Title500, page_params
from app.deps import AuthContext, get_current_user
from app.errors import InvalidInputError
from app.services import video_service

router = APIRouter(tags=["videos"])

MAX_DURATION_MS = 14_400_000  # 約 4 時間


def _unique_ids(values: list[int] | None) -> list[int] | None:
    if values is not None and len(set(values)) != len(values):
        raise ValueError("重複した識別子")
    return values


class VideoCreate(BaseModel):
    title: Title500
    description: str | None = None
    series_id: int | None = None
    episode_number: Annotated[int, Field(ge=1)] | None = None
    episode_title: Text500 | None = None
    sort_order: Annotated[int, Field(ge=0)] = 0
    duration_ms: Annotated[int, Field(ge=1, le=MAX_DURATION_MS)]
    mime_type: Annotated[str, Field(min_length=1, max_length=100)] = "video/mp4"
    genre_ids: list[int] = []

    _genres_unique = field_validator("genre_ids")(_unique_ids)


class VideoUpdate(BaseModel):
    """指定した項目だけを更新する。duration_ms などの変更できない項目は受け付けない。"""

    model_config = ConfigDict(extra="forbid")

    title: Title500 | None = None
    description: str | None = None
    series_id: int | None = None
    episode_number: Annotated[int, Field(ge=1)] | None = None
    episode_title: Text500 | None = None
    sort_order: Annotated[int, Field(ge=0)] | None = None
    genre_ids: list[int] | None = None

    _genres_unique = field_validator("genre_ids")(_unique_ids)


@router.get("/videos")
def list_videos(
    paging: Page = Depends(page_params),
    genre_id: int | None = Query(None),
    series_id: int | None = Query(None),
    status: str = Query("ready", pattern="^(ready|uploading|error|all)$"),
    q: str | None = Query(None),
    sort: str = Query("created_at", pattern="^(created_at|title|last_played_at)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    return video_service.list_videos(
        auth.user.id,
        paging,
        genre_id=genre_id,
        series_id=series_id,
        status=status,
        q=q,
        sort=sort,
        order=order,
    )


@router.post("/videos", status_code=201)
def create_video(body: VideoCreate, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    fields = body.model_dump(exclude={"genre_ids"})
    return video_service.create_video(auth.user.id, fields, body.genre_ids)


@router.get("/videos/{video_id}")
def get_video(video_id: int, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return video_service.get_video(auth.user.id, video_id)


@router.patch("/videos/{video_id}")
def update_video(
    video_id: int, body: VideoUpdate, auth: AuthContext = Depends(get_current_user)
) -> dict[str, Any]:
    provided = body.model_fields_set
    # null を許す項目以外に null が指定されたときは入力不正
    for name in ("title", "sort_order", "genre_ids"):
        if name in provided and getattr(body, name) is None:
            raise InvalidInputError(reason=f"{name} に null は指定できない")
    fields = {name: getattr(body, name) for name in provided if name != "genre_ids"}
    return video_service.update_video(
        auth.user.id, video_id, fields, body.genre_ids if "genre_ids" in provided else None
    )


@router.delete("/videos/{video_id}", status_code=204)
def delete_video(video_id: int, auth: AuthContext = Depends(get_current_user)) -> Response:
    video_service.delete_video(auth.user.id, video_id)
    return Response(status_code=204)
