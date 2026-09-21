from __future__ import annotations

from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from app.deps import AuthContext, get_current_user
from app.services import part_service

router = APIRouter(tags=["parts"])

# ヘッダの filename="..." に、そのまま入れられない文字
_UNSAFE = chr(34) + chr(92)


class PartCreateBody(BaseModel):
    type: str
    data: str | None = None
    filename: str | None = None
    title: str | None = None
    markers: list[Any] | None = None
    image_scale: float | None = None


class PartUpdateBody(BaseModel):
    type: str | None = None
    data: str | None = None
    filename: str | None = None
    title: str | None = None
    markers: list[Any] | None = None
    image_scale: float | None = None


class SwapBody(BaseModel):
    part_id_1: int
    part_id_2: int


def _content_response(item: dict[str, Any], download: bool) -> Response:
    filename: str = item["filename"]
    disposition = "inline" if item["inline"] and not download else "attachment"
    ascii_name = "".join(c if 32 <= ord(c) < 127 and c not in _UNSAFE else "_" for c in filename)
    header = f"{disposition}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename, safe='')}"
    return Response(
        content=item["content"],
        media_type=item["media_type"],
        headers={"Content-Disposition": header, "Cache-Control": "private, no-cache"},
    )


@router.post("/files/{file_id}/parts", status_code=201)
def create_part(file_id: int, body: PartCreateBody, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return part_service.create_part(auth.user.id, file_id, body.model_dump())


@router.post("/parts/swap-order", status_code=204)
def swap_order(body: SwapBody, auth: AuthContext = Depends(get_current_user)) -> Response:
    part_service.swap_order(auth.user.id, body.part_id_1, body.part_id_2)
    return Response(status_code=204)


@router.patch("/parts/{part_id}")
def update_part(part_id: int, body: PartUpdateBody, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return part_service.update_part(auth.user.id, part_id, body.model_dump(), set(body.model_fields_set))


@router.delete("/parts/{part_id}", status_code=204)
def delete_part(part_id: int, auth: AuthContext = Depends(get_current_user)) -> Response:
    part_service.delete_part(auth.user.id, part_id)
    return Response(status_code=204)


@router.post("/parts/{part_id}/undelete")
def undelete_part(part_id: int, auth: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    return part_service.undelete_part(auth.user.id, part_id)


@router.get("/parts/{part_id}/content")
def get_content(part_id: int, download: bool = False, auth: AuthContext = Depends(get_current_user)) -> Response:
    return _content_response(part_service.get_content(auth.user.id, part_id), download)


@router.get("/part-revisions/{revision_id}/content")
def get_revision_content(revision_id: int, auth: AuthContext = Depends(get_current_user)) -> Response:
    return _content_response(part_service.get_revision_content(auth.user.id, revision_id), True)
