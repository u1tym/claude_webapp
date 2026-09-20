from __future__ import annotations

from typing import Any

from psycopg2.extensions import cursor as PgCursor

from app.common import Page, build_pagination
from app.db import get_conn
from app.errors import InvalidInputError, NotFoundError, UnprocessableError
from app.logger import write
from app.repos import chunk as chunk_repo
from app.repos import playback as playback_repo
from app.repos import playlist as playlist_repo


def _owned(cur: PgCursor, user_id: int, playlist_id: int, *, lock: bool = False) -> dict[str, Any]:
    playlist = playlist_repo.get_playlist(cur, user_id, playlist_id, lock=lock)
    if playlist is None:
        raise NotFoundError(reason=f"プレイリストなし user_id={user_id} playlist_id={playlist_id}")
    return playlist


def _detail(cur: PgCursor, playlist: dict[str, Any]) -> dict[str, Any]:
    return {**playlist, "items": playlist_repo.list_items(cur, playlist["id"])}


def list_playlists(user_id: int, paging: Page) -> dict[str, Any]:
    with get_conn() as conn, conn.cursor() as cur:
        total = playlist_repo.count_playlists(cur, user_id)
        items = playlist_repo.list_playlists(cur, user_id, paging.per_page, paging.offset)
    write("INF", f"プレイリスト一覧 user_id={user_id} 件数={len(items)}/{total}")
    return {"items": items, "pagination": build_pagination(paging, total).model_dump()}


def create_playlist(user_id: int, name: str, description: str | None) -> dict[str, Any]:
    write("INF", f"プレイリスト作成要求 user_id={user_id} name={name}")
    with get_conn() as conn, conn.cursor() as cur:
        playlist = playlist_repo.insert_playlist(cur, user_id, name, description)
        detail = _detail(cur, playlist)
    write("INF", f"プレイリスト作成成功 user_id={user_id} playlist_id={playlist['id']}")
    return detail


def get_playlist(user_id: int, playlist_id: int) -> dict[str, Any]:
    with get_conn() as conn, conn.cursor() as cur:
        return _detail(cur, _owned(cur, user_id, playlist_id))


def update_playlist(user_id: int, playlist_id: int, fields: dict[str, Any]) -> dict[str, Any]:
    write("INF", f"プレイリスト編集要求 user_id={user_id} playlist_id={playlist_id} 項目={sorted(fields)}")
    if not fields:
        raise InvalidInputError(reason="更新項目なし")
    with get_conn() as conn, conn.cursor() as cur:
        _owned(cur, user_id, playlist_id, lock=True)
        playlist_repo.update_fields(cur, playlist_id, fields)
        detail = _detail(cur, _owned(cur, user_id, playlist_id))
    write("INF", f"プレイリスト編集成功 user_id={user_id} playlist_id={playlist_id}")
    return detail


def delete_playlist(user_id: int, playlist_id: int) -> None:
    write("INF", f"プレイリスト削除要求 user_id={user_id} playlist_id={playlist_id}")
    with get_conn() as conn, conn.cursor() as cur:
        _owned(cur, user_id, playlist_id, lock=True)
        playlist_repo.delete_playlist(cur, playlist_id)
    write("INF", f"プレイリスト削除成功 user_id={user_id} playlist_id={playlist_id}")


def replace_items(user_id: int, playlist_id: int, video_ids: list[int]) -> dict[str, Any]:
    write(
        "INF",
        f"プレイリスト項目の置換要求 user_id={user_id} playlist_id={playlist_id} 件数={len(video_ids)}",
    )
    with get_conn() as conn, conn.cursor() as cur:
        _owned(cur, user_id, playlist_id, lock=True)
        unique_ids = set(video_ids)
        if unique_ids and playlist_repo.count_owned_videos(cur, user_id, sorted(unique_ids)) != len(unique_ids):
            raise NotFoundError(reason=f"動画なし user_id={user_id} video_ids={sorted(unique_ids)}")
        playlist_repo.replace_items(cur, playlist_id, video_ids)
        playlist_repo.touch(cur, playlist_id)
        detail = _detail(cur, _owned(cur, user_id, playlist_id))
    write("INF", f"プレイリスト項目の置換成功 user_id={user_id} playlist_id={playlist_id}")
    return detail


# ---- 再生 -------------------------------------------------------------


def _playback_item(
    cur: PgCursor, user_id: int, playlist_id: int, item: dict[str, Any], position_ms: int
) -> dict[str, Any]:
    """再生する項目の情報。再生できる項目なら、再生の開始を記録し、続きから視聴を更新する。

    再生できない項目（動画が登録中・エラー）も返す（フロントが理由を示し、前後へ移動できるように）。
    """
    playable = item["status"] == "ready"
    if not playable:
        position_ms = 0
    elif position_ms >= item["duration_ms"]:
        position_ms = 0  # 動画の長さを超える位置、および末尾の位置（視聴完了）は、先頭から再生する
    start_chunk = None
    if playable:
        found = chunk_repo.find_chunk_at(cur, item["video_id"], position_ms)
        if found is not None:
            start_chunk = {
                "chunk_index": found["chunk_index"],
                "start_time_ms": found["start_time_ms"],
                "end_time_ms": found["end_time_ms"],
                "byte_length": found["byte_length"],
            }
        playback_repo.record_play_start(cur, user_id, item["video_id"])
    playback_repo.upsert_playlist_context(cur, user_id, playlist_id, item["item_id"], position_ms)
    return {
        "playlist_id": playlist_id,
        "item_id": item["item_id"],
        "video_id": item["video_id"],
        "title": item["title"],
        "duration_ms": item["duration_ms"],
        "mime_type": item["mime_type"],
        "status": item["status"],
        "position_ms": position_ms,
        "sort_order": item["sort_order"],
        "has_next": playlist_repo.has_adjacent(cur, playlist_id, item["sort_order"], forward=True),
        "has_prev": playlist_repo.has_adjacent(cur, playlist_id, item["sort_order"], forward=False),
        "start_chunk": start_chunk,
    }


def start_playback(user_id: int, playlist_id: int, resume: bool) -> dict[str, Any]:
    write("INF", f"プレイリスト再生開始要求 user_id={user_id} playlist_id={playlist_id} resume={resume}")
    with get_conn() as conn, conn.cursor() as cur:
        _owned(cur, user_id, playlist_id)
        item: dict[str, Any] | None = None
        position_ms = 0
        if resume:
            context = playback_repo.get_context(cur, user_id)
            if (
                context is not None
                and context["last_playlist_id"] == playlist_id
                and context["last_playlist_item_id"] is not None
            ):
                item = playlist_repo.get_item(cur, playlist_id, context["last_playlist_item_id"])
                position_ms = context["last_playlist_position_ms"]
        if item is None:
            position_ms = 0
            item = playlist_repo.first_item(cur, playlist_id)
        if item is None:
            raise UnprocessableError(
                "プレイリストに動画がありません", reason=f"空のプレイリストの再生 playlist_id={playlist_id}"
            )
        result = _playback_item(cur, user_id, playlist_id, item, position_ms)
    write(
        "INF",
        f"プレイリスト再生開始 user_id={user_id} playlist_id={playlist_id} item_id={result['item_id']}"
        f" position_ms={result['position_ms']}",
    )
    return result


def _move(user_id: int, playlist_id: int, item_id: int, *, forward: bool) -> dict[str, Any] | None:
    with get_conn() as conn, conn.cursor() as cur:
        _owned(cur, user_id, playlist_id)
        current = playlist_repo.get_item(cur, playlist_id, item_id)
        if current is None:
            raise NotFoundError(reason=f"項目なし playlist_id={playlist_id} item_id={item_id}")
        target = playlist_repo.adjacent_item(cur, playlist_id, current["sort_order"], forward=forward)
        if target is None:
            return None
        result = _playback_item(cur, user_id, playlist_id, target, 0)
    write(
        "INF",
        f"プレイリストの{'次' if forward else '前'}へ user_id={user_id} playlist_id={playlist_id}"
        f" item_id={result['item_id']}",
    )
    return result


def next_item(user_id: int, playlist_id: int, item_id: int) -> dict[str, Any]:
    item = _move(user_id, playlist_id, item_id, forward=True)
    return {"has_next": item is not None, "item": item}


def prev_item(user_id: int, playlist_id: int, item_id: int) -> dict[str, Any]:
    item = _move(user_id, playlist_id, item_id, forward=False)
    return {"has_prev": item is not None, "item": item}


def save_item_state(
    user_id: int, playlist_id: int, item_id: int, position_ms: int, completed: bool
) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        _owned(cur, user_id, playlist_id)
        item = playlist_repo.get_item(cur, playlist_id, item_id)
        if item is None:
            raise NotFoundError(reason=f"項目なし playlist_id={playlist_id} item_id={item_id}")
        if position_ms < 0 or position_ms > item["duration_ms"]:
            raise InvalidInputError(
                reason=f"再生位置が範囲外 item_id={item_id} position_ms={position_ms} duration_ms={item['duration_ms']}"
            )
        playback_repo.save_state(cur, user_id, item["video_id"], position_ms, completed)
        playback_repo.upsert_playlist_context(cur, user_id, playlist_id, item_id, position_ms)
    if completed:
        write("INF", f"視聴完了 user_id={user_id} video_id={item['video_id']} playlist_id={playlist_id}")
