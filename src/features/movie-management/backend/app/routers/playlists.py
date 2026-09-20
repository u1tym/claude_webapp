from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field

from app.common import Page, Title500, page_params
from app.deps import AuthContext, get_current_user
from app.errors import InvalidInputError
from app.services import playlist_service

router = APIRouter(tags=["playlists"])


class PlaylistCreate(BaseModel):
    name: Title500
    description: str | None = None


class PlaylistUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Title500 | None = None
    description: str | None = None


class ItemBody(BaseModel):
    video_id: int


class ItemsBody(BaseModel):
    items: list[ItemBody]


class StartBody(BaseModel):
    resume: bool = True


class StateBody(BaseModel):
    position_ms: Annotated[int, Field(ge=0)]
    completed: bool = False


@router.get("/playlists")
def list_playlists(
    paging: Page = Depends(page_params), auth: AuthContext = Depends(get_current_user)
) -> dict[str, Any]:
    return playlist_service.list_playlists(auth.user.id, paging)


@router.post("/playlists", status_code=201)
def create_playlist(body: PlaylistCreate, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return playlist_service.create_playlist(auth.user.id, body.name, body.description)


@router.get("/playlists/{playlist_id}")
def get_playlist(playlist_id: int, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return playlist_service.get_playlist(auth.user.id, playlist_id)


@router.patch("/playlists/{playlist_id}")
def update_playlist(
    playlist_id: int, body: PlaylistUpdate, auth: AuthContext = Depends(get_current_user)
) -> dict[str, Any]:
    provided = body.model_fields_set
    if "name" in provided and body.name is None:
        raise InvalidInputError(reason="name に null は指定できない")
    fields = {name: getattr(body, name) for name in provided}
    return playlist_service.update_playlist(auth.user.id, playlist_id, fields)


@router.delete("/playlists/{playlist_id}", status_code=204)
def delete_playlist(playlist_id: int, auth: AuthContext = Depends(get_current_user)) -> Response:
    playlist_service.delete_playlist(auth.user.id, playlist_id)
    return Response(status_code=204)


@router.put("/playlists/{playlist_id}/items")
def replace_items(
    playlist_id: int, body: ItemsBody, auth: AuthContext = Depends(get_current_user)
) -> dict[str, Any]:
    return playlist_service.replace_items(auth.user.id, playlist_id, [item.video_id for item in body.items])


@router.post("/playlists/{playlist_id}/playback/start")
def start_playback(
    playlist_id: int, body: StartBody | None = None, auth: AuthContext = Depends(get_current_user)
) -> dict[str, Any]:
    resume = body.resume if body is not None else True
    return playlist_service.start_playback(auth.user.id, playlist_id, resume)


@router.get("/playlists/{playlist_id}/items/{item_id}/next")
def next_item(playlist_id: int, item_id: int, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return playlist_service.next_item(auth.user.id, playlist_id, item_id)


@router.get("/playlists/{playlist_id}/items/{item_id}/prev")
def prev_item(playlist_id: int, item_id: int, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return playlist_service.prev_item(auth.user.id, playlist_id, item_id)


@router.put("/playlists/{playlist_id}/items/{item_id}/playback/state", status_code=204)
def save_item_state(
    playlist_id: int, item_id: int, body: StateBody, auth: AuthContext = Depends(get_current_user)
) -> Response:
    playlist_service.save_item_state(auth.user.id, playlist_id, item_id, body.position_ms, body.completed)
    return Response(status_code=204)
