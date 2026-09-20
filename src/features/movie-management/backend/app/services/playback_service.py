from __future__ import annotations

from typing import Any

from app.common import Page, build_pagination
from app.db import get_conn
from app.errors import InvalidInputError, NotFoundError, UnprocessableError
from app.logger import write
from app.repos import chunk as chunk_repo
from app.repos import playback as playback_repo
from app.repos import video as video_repo


def _chunk_meta(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "chunk_index": row["chunk_index"],
        "start_time_ms": row["start_time_ms"],
        "end_time_ms": row["end_time_ms"],
        "byte_length": row["byte_length"],
    }


def start_playback(user_id: int, video_id: int, resume: bool) -> dict[str, Any]:
    write("INF", f"再生開始要求 user_id={user_id} video_id={video_id} resume={resume}")
    with get_conn() as conn, conn.cursor() as cur:
        video = video_repo.get_owned(cur, user_id, video_id)
        if video is None:
            raise NotFoundError(reason=f"動画なし user_id={user_id} video_id={video_id}")
        if video["status"] != "ready":
            raise UnprocessableError(
                "再生できない動画です", reason=f"再生不可の動画の再生開始 video_id={video_id} status={video['status']}"
            )
        previous = playback_repo.get_state(cur, user_id, video_id)
        position_ms = previous["position_ms"] if (resume and previous is not None) else 0
        # 動画の長さを超える位置、および末尾の位置（視聴完了で保存される）は、先頭から再生する
        if position_ms >= video["duration_ms"]:
            position_ms = 0
        state = playback_repo.record_play_start(cur, user_id, video_id)
        playback_repo.upsert_video_context(cur, user_id, video_id, position_ms)
        start_chunk = chunk_repo.find_chunk_at(cur, video_id, position_ms)
    write("INF", f"再生開始 user_id={user_id} video_id={video_id} position_ms={position_ms}")
    return {
        "id": video_id,
        "title": video["title"],
        "duration_ms": video["duration_ms"],
        "mime_type": video["mime_type"],
        "chunk_count": video["chunk_count"],
        "position_ms": position_ms,
        "completed": state["completed"],
        "status": video["status"],
        "start_chunk": _chunk_meta(start_chunk),
    }


def save_state(user_id: int, video_id: int, position_ms: int, completed: bool) -> dict[str, Any]:
    with get_conn() as conn, conn.cursor() as cur:
        video = video_repo.get_owned(cur, user_id, video_id)
        if video is None:
            raise NotFoundError(reason=f"動画なし user_id={user_id} video_id={video_id}")
        if position_ms < 0 or position_ms > video["duration_ms"]:
            raise InvalidInputError(
                reason=f"再生位置が範囲外 video_id={video_id} position_ms={position_ms} duration_ms={video['duration_ms']}"
            )
        last_played_at = playback_repo.save_state(cur, user_id, video_id, position_ms, completed)
        playback_repo.upsert_video_context(cur, user_id, video_id, position_ms)
    if completed:
        write("INF", f"視聴完了 user_id={user_id} video_id={video_id}")
    return {
        "video_id": video_id,
        "position_ms": position_ms,
        "completed": completed,
        "last_played_at": last_played_at,
    }


def next_video(user_id: int, video_id: int) -> dict[str, Any]:
    with get_conn() as conn, conn.cursor() as cur:
        current = playback_repo.get_video_for_next(cur, user_id, video_id)
        if current is None:
            raise NotFoundError(reason=f"動画なし user_id={user_id} video_id={video_id}")
        if current["series_id"] is not None:
            found = playback_repo.next_in_series(cur, user_id, current)
        else:
            found = playback_repo.next_standalone(cur, user_id, current)
    if found is None:
        return {"has_next": False, "video": None}
    return {"has_next": True, "video": found}


def list_history(user_id: int, paging: Page) -> dict[str, Any]:
    with get_conn() as conn, conn.cursor() as cur:
        total = playback_repo.count_history(cur, user_id)
        items = playback_repo.list_history(cur, user_id, paging.per_page, paging.offset)
    write("INF", f"視聴履歴 user_id={user_id} 件数={len(items)}/{total}")
    return {"items": items, "pagination": build_pagination(paging, total).model_dump()}


def last_playback(user_id: int) -> dict[str, Any]:
    with get_conn() as conn, conn.cursor() as cur:
        video = playback_repo.last_video(cur, user_id)
        playlist = playback_repo.last_playlist(cur, user_id)
    return {"video": video, "playlist": playlist}
