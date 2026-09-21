from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from app.common import Required
from app.deps import AuthContext, get_current_user
from app.services import file_service, part_service

router = APIRouter(tags=["files"])


class FileCreateBody(BaseModel):
    folder_id: int
    title: Required


class FileRenameBody(BaseModel):
    title: Required


class FileMoveBody(BaseModel):
    new_folder_id: int


class SwapBody(BaseModel):
    file_id_1: int
    file_id_2: int


@router.post("/files", status_code=201)
def create_file(body: FileCreateBody, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return file_service.create_file(auth.user.id, body.folder_id, body.title)


@router.post("/files/swap-order", status_code=204)
def swap_order(body: SwapBody, auth: AuthContext = Depends(get_current_user)) -> Response:
    file_service.swap_order(auth.user.id, body.file_id_1, body.file_id_2)
    return Response(status_code=204)


@router.get("/files/{file_id}")
def get_file(
    file_id: int,
    include_deleted_parts: bool = False,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    return part_service.get_file_detail(auth.user.id, file_id, include_deleted_parts)


@router.patch("/files/{file_id}")
def rename_file(file_id: int, body: FileRenameBody, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return file_service.rename_file(auth.user.id, file_id, body.title)


@router.post("/files/{file_id}/move")
def move_file(file_id: int, body: FileMoveBody, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return file_service.move_file(auth.user.id, file_id, body.new_folder_id)


@router.delete("/files/{file_id}", status_code=204)
def delete_file(file_id: int, auth: AuthContext = Depends(get_current_user)) -> Response:
    file_service.delete_file(auth.user.id, file_id)
    return Response(status_code=204)


@router.post("/files/{file_id}/undelete")
def undelete_file(file_id: int, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return file_service.undelete_file(auth.user.id, file_id)
