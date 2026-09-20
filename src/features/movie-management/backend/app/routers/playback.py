from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.common import Page, page_params
from app.deps import AuthContext, get_current_user
from app.services import playback_service

router = APIRouter(tags=["playback"])


class StartBody(BaseModel):
    resume: bool = True


class StateBody(BaseModel):
    position_ms: Annotated[int, Field(ge=0)]
    completed: bool = False


@router.post("/videos/{video_id}/playback/start")
def start_playback(
    video_id: int, body: StartBody | None = None, auth: AuthContext = Depends(get_current_user)
) -> dict[str, Any]:
    resume = body.resume if body is not None else True
    return playback_service.start_playback(auth.user.id, video_id, resume)


@router.put("/videos/{video_id}/playback/state")
def save_state(
    video_id: int, body: StateBody, auth: AuthContext = Depends(get_current_user)
) -> dict[str, Any]:
    return playback_service.save_state(auth.user.id, video_id, body.position_ms, body.completed)


@router.get("/videos/{video_id}/next")
def next_video(video_id: int, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return playback_service.next_video(auth.user.id, video_id)


@router.get("/playback/history")
def list_history(
    paging: Page = Depends(page_params), auth: AuthContext = Depends(get_current_user)
) -> dict[str, Any]:
    return playback_service.list_history(auth.user.id, paging)


@router.get("/playback/last")
def last_playback(auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return playback_service.last_playback(auth.user.id)
