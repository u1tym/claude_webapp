from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from app.common import Required
from app.deps import AuthContext, get_current_user
from app.services import folder_service

router = APIRouter(tags=["folders"])


class FolderCreateBody(BaseModel):
    parent_id: int | None
    name: Required


class FolderRenameBody(BaseModel):
    name: Required


class FolderMoveBody(BaseModel):
    new_parent_id: int | None


class SwapBody(BaseModel):
    folder_id_1: int
    folder_id_2: int


@router.get("/items")
def list_items(
    folder_id: int | None = None,
    include_deleted: bool = False,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    return folder_service.list_items(auth.user.id, folder_id, include_deleted)


@router.post("/folders", status_code=201)
def create_folder(body: FolderCreateBody, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return folder_service.create_folder(auth.user.id, body.parent_id, body.name)


# "/folders/swap-order" は "/folders/{folder_id}" 系より先に定義する
@router.post("/folders/swap-order", status_code=204)
def swap_order(body: SwapBody, auth: AuthContext = Depends(get_current_user)) -> Response:
    folder_service.swap_order(auth.user.id, body.folder_id_1, body.folder_id_2)
    return Response(status_code=204)


@router.patch("/folders/{folder_id}")
def rename_folder(
    folder_id: int, body: FolderRenameBody, auth: AuthContext = Depends(get_current_user)
) -> dict[str, Any]:
    return folder_service.rename_folder(auth.user.id, folder_id, body.name)


@router.post("/folders/{folder_id}/move")
def move_folder(folder_id: int, body: FolderMoveBody, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return folder_service.move_folder(auth.user.id, folder_id, body.new_parent_id)


@router.delete("/folders/{folder_id}", status_code=204)
def delete_folder(folder_id: int, auth: AuthContext = Depends(get_current_user)) -> Response:
    folder_service.delete_folder(auth.user.id, folder_id)
    return Response(status_code=204)


@router.post("/folders/{folder_id}/undelete")
def undelete_folder(folder_id: int, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return folder_service.undelete_folder(auth.user.id, folder_id)
