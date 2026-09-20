from __future__ import annotations

from typing import Any

from app.db import get_conn
from app.errors import InvalidInputError, NotFoundError
from app.logger import write
from app.repos import thumbnail as thumbnail_repo
from app.repos import video as video_repo

MAX_THUMBNAIL_BYTES = 5 * 1024 * 1024  # 5 MiB


def put_thumbnail(
    user_id: int,
    video_id: int,
    data: bytes,
    mime_type: str,
    width: int | None,
    height: int | None,
) -> dict[str, Any]:
    if not data or len(data) > MAX_THUMBNAIL_BYTES:
        raise InvalidInputError(reason=f"サムネイルのサイズ不正 bytes={len(data)}")
    if not mime_type.startswith("image/") or len(mime_type) > 50:
        raise InvalidInputError(reason=f"サムネイルの形式不正 mime_type={mime_type}")
    if (width is not None and width < 1) or (height is not None and height < 1):
        raise InvalidInputError(reason=f"サムネイルの寸法不正 width={width} height={height}")
    with get_conn() as conn, conn.cursor() as cur:
        if video_repo.get_owned(cur, user_id, video_id) is None:
            raise NotFoundError(reason=f"動画なし user_id={user_id} video_id={video_id}")
        thumbnail_repo.upsert_thumbnail(cur, video_id, mime_type, width, height, data)
    write("INF", f"サムネイル登録成功 user_id={user_id} video_id={video_id} bytes={len(data)}")
    return {"video_id": video_id, "mime_type": mime_type, "width": width, "height": height}


def get_thumbnail(user_id: int, video_id: int) -> dict[str, Any]:
    with get_conn() as conn, conn.cursor() as cur:
        thumbnail = thumbnail_repo.get_thumbnail(cur, user_id, video_id)
    if thumbnail is None:
        raise NotFoundError(reason=f"サムネイルなし user_id={user_id} video_id={video_id}")
    return thumbnail
