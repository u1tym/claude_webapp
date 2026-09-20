"""動画ファイルの登録（チャンクの受信・完了）と差し替えの開始。"""

from __future__ import annotations

from typing import Any

from psycopg2 import errors

from app.db import get_conn
from app.errors import ConflictError, InvalidInputError, NotFoundError, UnprocessableError
from app.logger import write
from app.repos import chunk as chunk_repo
from app.repos import video as video_repo

MAX_CHUNK_BYTES = 8 * 1024 * 1024  # 8 MiB

NOT_UPLOADING = "登録中の動画ではありません"
COUNT_MISMATCH = "チャンク数が一致しません"


def upload_chunk(
    user_id: int,
    video_id: int,
    chunk_index: int,
    start_time_ms: int,
    end_time_ms: int,
    data: bytes,
) -> dict[str, Any]:
    if chunk_index < 0 or start_time_ms < 0 or end_time_ms <= start_time_ms:
        raise InvalidInputError(reason=f"チャンクの範囲不正 index={chunk_index} {start_time_ms}-{end_time_ms}")
    if not data or len(data) > MAX_CHUNK_BYTES:
        raise InvalidInputError(reason=f"チャンクのサイズ不正 bytes={len(data)}")
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # 同じ動画へのチャンク受信を直列にし、チャンク数・サイズの加算を正しく保つ
            video = video_repo.get_owned(cur, user_id, video_id, lock=True)
            if video is None:
                raise NotFoundError(reason=f"動画なし user_id={user_id} video_id={video_id}")
            if video["status"] != "uploading":
                raise UnprocessableError(
                    NOT_UPLOADING, reason=f"登録中でない動画へのチャンク video_id={video_id} status={video['status']}"
                )
            chunk_repo.insert_chunk(cur, video_id, chunk_index, start_time_ms, end_time_ms, data)
            uploaded = chunk_repo.add_to_video_totals(cur, video_id, len(data))
    except errors.UniqueViolation:
        raise ConflictError(
            "同じチャンクが登録済みです", reason=f"チャンク重複 video_id={video_id} index={chunk_index}"
        ) from None
    if chunk_index == 0:
        write("INF", f"動画ファイル登録開始 user_id={user_id} video_id={video_id}")
    return {
        "video_id": video_id,
        "chunk_index": chunk_index,
        "byte_length": len(data),
        "uploaded_chunks": uploaded,
    }


def complete_upload(user_id: int, video_id: int, duration_ms: int, chunk_count: int) -> dict[str, Any]:
    write(
        "INF",
        f"動画ファイル登録完了要求 user_id={user_id} video_id={video_id}"
        f" duration_ms={duration_ms} chunk_count={chunk_count}",
    )
    with get_conn() as conn, conn.cursor() as cur:
        video = video_repo.get_owned(cur, user_id, video_id, lock=True)
        if video is None:
            raise NotFoundError(reason=f"動画なし user_id={user_id} video_id={video_id}")
        if video["status"] != "uploading":
            raise UnprocessableError(
                NOT_UPLOADING, reason=f"登録中でない動画の完了 video_id={video_id} status={video['status']}"
            )
        stats = chunk_repo.stats(cur, video_id)
        # チャンクが無い、件数が違う、番号が 0 から連続していない場合は再生可能にしない
        if (
            stats["chunk_count"] == 0
            or stats["chunk_count"] != chunk_count
            or stats["max_index"] != stats["chunk_count"] - 1
        ):
            raise UnprocessableError(
                COUNT_MISMATCH,
                reason=f"チャンク不整合 video_id={video_id} 登録済み={stats['chunk_count']}"
                f" 通知={chunk_count} 最大番号={stats['max_index']}",
            )
        chunk_repo.mark_ready(cur, video_id, duration_ms, stats["chunk_count"], stats["total_bytes"])
    write(
        "INF",
        f"動画ファイル登録完了 user_id={user_id} video_id={video_id}"
        f" chunk_count={stats['chunk_count']} bytes={stats['total_bytes']}",
    )
    return {
        "id": video_id,
        "status": "ready",
        "duration_ms": duration_ms,
        "chunk_count": stats["chunk_count"],
        "file_size_bytes": stats["total_bytes"],
    }


def start_replace(user_id: int, video_id: int, duration_ms: int, mime_type: str) -> dict[str, Any]:
    write(
        "INF",
        f"動画ファイル差し替え要求 user_id={user_id} video_id={video_id}"
        f" duration_ms={duration_ms} mime_type={mime_type}",
    )
    with get_conn() as conn, conn.cursor() as cur:
        if video_repo.get_owned(cur, user_id, video_id, lock=True) is None:
            raise NotFoundError(reason=f"動画なし user_id={user_id} video_id={video_id}")
        chunk_repo.delete_chunks(cur, video_id)
        chunk_repo.reset_for_replace(cur, video_id, duration_ms, mime_type)
    write("INF", f"動画ファイル差し替え開始 user_id={user_id} video_id={video_id}")
    return {"id": video_id, "status": "uploading", "chunk_count": 0}
