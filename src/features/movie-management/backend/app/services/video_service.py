from __future__ import annotations

from typing import Any

from psycopg2 import errors
from psycopg2.extensions import cursor as PgCursor

from app.common import Page, build_pagination, like_pattern
from app.db import get_conn
from app.errors import ConflictError, InvalidInputError, NotFoundError
from app.logger import write
from app.repos import genre as genre_repo
from app.repos import series as series_repo
from app.repos import video as video_repo

EPISODE_CONFLICT = "話数が重複しています"


def _check_series(cur: PgCursor, user_id: int, series_id: int | None) -> None:
    if series_id is not None and series_repo.get_series(cur, user_id, series_id) is None:
        raise NotFoundError(reason=f"作品なし user_id={user_id} series_id={series_id}")


def _check_genres(cur: PgCursor, user_id: int, genre_ids: list[int]) -> None:
    if genre_ids and genre_repo.count_accessible(cur, user_id, genre_ids) != len(genre_ids):
        raise NotFoundError(reason=f"ジャンルなし user_id={user_id} genre_ids={genre_ids}")


def _summary(row: dict[str, Any], genres: list[dict[str, Any]]) -> dict[str, Any]:
    """一覧の要素（VideoSummary）。詳細用の列を除く。"""
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "series_id": row["series_id"],
        "series_title": row["series_title"],
        "episode_number": row["episode_number"],
        "episode_title": row["episode_title"],
        "sort_order": row["sort_order"],
        "duration_ms": row["duration_ms"],
        "mime_type": row["mime_type"],
        "file_size_bytes": row["file_size_bytes"],
        "status": row["status"],
        "genres": genres,
        "has_thumbnail": row["has_thumbnail"],
        "position_ms": row["position_ms"],
        "completed": row["completed"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _detail(cur: PgCursor, user_id: int, video_id: int) -> dict[str, Any]:
    row = video_repo.get_detail(cur, user_id, video_id)
    if row is None:
        raise NotFoundError(reason=f"動画なし user_id={user_id} video_id={video_id}")
    genres = video_repo.genres_for_videos(cur, [video_id])[video_id]
    return {
        **_summary(row, genres),
        "chunk_count": row["chunk_count"],
        "play_count": row["play_count"],
        "last_played_at": row["last_played_at"],
    }


def create_video(user_id: int, fields: dict[str, Any], genre_ids: list[int]) -> dict[str, Any]:
    write(
        "INF",
        f"動画登録要求 user_id={user_id} title={fields['title']} series_id={fields['series_id']}"
        f" duration_ms={fields['duration_ms']} genre_ids={genre_ids}",
    )
    try:
        with get_conn() as conn, conn.cursor() as cur:
            _check_series(cur, user_id, fields["series_id"])
            _check_genres(cur, user_id, genre_ids)
            created = video_repo.insert_video(cur, user_id, **fields)
            video_repo.replace_genres(cur, created["id"], genre_ids)
    except errors.UniqueViolation:
        raise ConflictError(EPISODE_CONFLICT, reason="話数重複") from None
    write("INF", f"動画登録成功 user_id={user_id} video_id={created['id']}")
    return created


def get_video(user_id: int, video_id: int) -> dict[str, Any]:
    with get_conn() as conn, conn.cursor() as cur:
        return _detail(cur, user_id, video_id)


def update_video(
    user_id: int, video_id: int, fields: dict[str, Any], genre_ids: list[int] | None
) -> dict[str, Any]:
    write("INF", f"動画編集要求 user_id={user_id} video_id={video_id} 項目={sorted(fields)}"
                 f" genre_ids={genre_ids}")
    if not fields and genre_ids is None:
        raise InvalidInputError(reason="更新項目なし")
    try:
        with get_conn() as conn, conn.cursor() as cur:
            if video_repo.get_owned(cur, user_id, video_id, lock=True) is None:
                raise NotFoundError(reason=f"動画なし user_id={user_id} video_id={video_id}")
            if "series_id" in fields:
                _check_series(cur, user_id, fields["series_id"])
            if genre_ids is not None:
                _check_genres(cur, user_id, genre_ids)
                video_repo.replace_genres(cur, video_id, genre_ids)
            video_repo.update_fields(cur, user_id, video_id, fields)
            detail = _detail(cur, user_id, video_id)
    except errors.UniqueViolation:
        raise ConflictError(EPISODE_CONFLICT, reason="話数重複") from None
    write("INF", f"動画編集成功 user_id={user_id} video_id={video_id}")
    return detail


def delete_video(user_id: int, video_id: int) -> None:
    write("INF", f"動画削除要求 user_id={user_id} video_id={video_id}")
    with get_conn() as conn, conn.cursor() as cur:
        if not video_repo.delete_video(cur, user_id, video_id):
            raise NotFoundError(reason=f"動画なし user_id={user_id} video_id={video_id}")
    write("INF", f"動画削除成功 user_id={user_id} video_id={video_id}")


def list_videos(
    user_id: int,
    paging: Page,
    *,
    genre_id: int | None,
    series_id: int | None,
    status: str,
    q: str | None,
    sort: str,
    order: str,
) -> dict[str, Any]:
    keyword = q.strip() if q else ""
    pattern = like_pattern(keyword) if keyword else None
    with get_conn() as conn, conn.cursor() as cur:
        total = video_repo.count_videos(cur, user_id, status, genre_id, series_id, pattern)
        rows = video_repo.list_videos(
            cur, user_id, status, genre_id, series_id, pattern, sort, order,
            paging.per_page, paging.offset,
        )
        genres = video_repo.genres_for_videos(cur, [row["id"] for row in rows])
    write(
        "INF",
        f"動画一覧 user_id={user_id} status={status} genre_id={genre_id} series_id={series_id}"
        f" q={keyword} sort={sort} order={order} 件数={len(rows)}/{total}",
    )
    return {
        "items": [_summary(row, genres[row["id"]]) for row in rows],
        "pagination": build_pagination(paging, total).model_dump(),
    }
