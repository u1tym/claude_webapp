"""動画ファイルに関わるエンドポイント（チャンクの登録・完了・差し替え・配信・サムネイル）。"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile
from fastapi.responses import Response, StreamingResponse
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.deps import AuthContext, get_current_user
from app.errors import InvalidInputError
from app.services import stream_service, thumbnail_service, upload_service

router = APIRouter(tags=["video-files"])

MAX_DURATION_MS = 14_400_000  # 約 4 時間


class CompleteBody(BaseModel):
    duration_ms: Annotated[int, Field(ge=1, le=MAX_DURATION_MS)]
    chunk_count: Annotated[int, Field(ge=1)]


class ReplaceBody(BaseModel):
    duration_ms: Annotated[int, Field(ge=1, le=MAX_DURATION_MS)]
    mime_type: Annotated[str, Field(min_length=1, max_length=100)] = "video/mp4"


@router.post("/videos/{video_id}/chunks", status_code=201)
async def upload_chunk(
    video_id: int,
    chunk_index: Annotated[int, Form()],
    start_time_ms: Annotated[int, Form()],
    end_time_ms: Annotated[int, Form()],
    data: Annotated[UploadFile, File()],
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    # 上限を超える本体を全部は読み込まない（超過を検出できる分だけ読む）
    content = await data.read(upload_service.MAX_CHUNK_BYTES + 1)
    return await run_in_threadpool(
        upload_service.upload_chunk,
        auth.user.id,
        video_id,
        chunk_index,
        start_time_ms,
        end_time_ms,
        content,
    )


@router.post("/videos/{video_id}/complete")
def complete_upload(
    video_id: int, body: CompleteBody, auth: AuthContext = Depends(get_current_user)
) -> dict[str, Any]:
    return upload_service.complete_upload(auth.user.id, video_id, body.duration_ms, body.chunk_count)


@router.post("/videos/{video_id}/replace")
def start_replace(
    video_id: int, body: ReplaceBody, auth: AuthContext = Depends(get_current_user)
) -> dict[str, Any]:
    return upload_service.start_replace(auth.user.id, video_id, body.duration_ms, body.mime_type)


@router.get("/videos/{video_id}/stream")
def stream_video(
    video_id: int,
    range_header: Annotated[str | None, Header(alias="Range")] = None,
    auth: AuthContext = Depends(get_current_user),
) -> StreamingResponse:
    plan = stream_service.prepare_stream(auth.user.id, video_id, range_header)
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(plan.content_length),
        "Cache-Control": "private",
    }
    if plan.content_range is not None:
        headers["Content-Range"] = plan.content_range
    return StreamingResponse(
        plan.body,
        status_code=plan.status_code,
        media_type=plan.media_type,
        headers=headers,
    )


@router.get("/videos/{video_id}/thumbnail")
def get_thumbnail(video_id: int, auth: AuthContext = Depends(get_current_user)) -> Response:
    thumbnail = thumbnail_service.get_thumbnail(auth.user.id, video_id)
    return Response(
        content=thumbnail["data"],
        media_type=thumbnail["mime_type"],
        headers={"Cache-Control": "private"},
    )


@router.put("/videos/{video_id}/thumbnail")
async def put_thumbnail(
    video_id: int,
    data: Annotated[UploadFile, File()],
    mime_type: Annotated[str, Form()] = "image/jpeg",
    width: Annotated[int | None, Form()] = None,
    height: Annotated[int | None, Form()] = None,
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    content = await data.read(thumbnail_service.MAX_THUMBNAIL_BYTES + 1)
    if not content:
        raise InvalidInputError(reason="サムネイルが空")
    return await run_in_threadpool(
        thumbnail_service.put_thumbnail, auth.user.id, video_id, content, mime_type, width, height
    )
