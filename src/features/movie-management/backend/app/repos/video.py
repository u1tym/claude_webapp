from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from psycopg2.extensions import cursor as PgCursor
from psycopg2.extras import execute_values

# 一覧・詳細で返す列。動画ファイルのデータ（video_chunks.data）は含めない。
_SUMMARY_SELECT = """
    SELECT v.id, v.title, v.description, v.series_id, s.title AS series_title,
           v.episode_number, v.episode_title, v.sort_order, v.duration_ms, v.mime_type,
           v.file_size_bytes, v.status, v.chunk_count, v.created_at, v.updated_at,
           EXISTS (SELECT 1 FROM movie_management.thumbnails t WHERE t.video_id = v.id) AS has_thumbnail,
           ps.position_ms AS position_ms,
           COALESCE(ps.completed, false) AS completed,
           COALESCE(ps.play_count, 0) AS play_count,
           ps.last_played_at AS last_played_at
    FROM movie_management.videos v
    LEFT JOIN movie_management.series s ON s.id = v.series_id
    LEFT JOIN movie_management.playback_states ps ON ps.video_id = v.id AND ps.user_id = %s
"""

# ORDER BY に埋め込むため、許可した組み合わせだけを使う
_SORT_COLUMNS = {
    "created_at": "v.created_at",
    "title": "v.title",
    "last_played_at": "ps.last_played_at",
}


def insert_video(
    cur: PgCursor,
    user_id: int,
    *,
    title: str,
    description: str | None,
    series_id: int | None,
    episode_number: int | None,
    episode_title: str | None,
    sort_order: int,
    duration_ms: int,
    mime_type: str,
) -> dict[str, Any]:
    cur.execute(
        """
        INSERT INTO movie_management.videos
            (user_id, series_id, title, description, episode_number, episode_title,
             sort_order, duration_ms, mime_type, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'uploading')
        RETURNING id, status, title, chunk_count, created_at
        """,
        (user_id, series_id, title, description, episode_number, episode_title,
         sort_order, duration_ms, mime_type),
    )
    return dict(cur.fetchone())


def get_owned(cur: PgCursor, user_id: int, video_id: int, *, lock: bool = False) -> dict[str, Any] | None:
    """本人の動画の基本情報。他ユーザ・存在しないものは None。"""
    cur.execute(
        f"""
        SELECT id, user_id, series_id, title, status, duration_ms, mime_type,
               file_size_bytes, chunk_count
        FROM movie_management.videos
        WHERE id = %s AND user_id = %s
        {"FOR UPDATE" if lock else ""}
        """,
        (video_id, user_id),
    )
    row = cur.fetchone()
    return dict(row) if row is not None else None


def get_detail(cur: PgCursor, user_id: int, video_id: int) -> dict[str, Any] | None:
    cur.execute(
        _SUMMARY_SELECT + " WHERE v.id = %s AND v.user_id = %s",
        (user_id, video_id, user_id),
    )
    row = cur.fetchone()
    return dict(row) if row is not None else None


def genres_for_videos(cur: PgCursor, video_ids: Sequence[int]) -> dict[int, list[dict[str, Any]]]:
    result: dict[int, list[dict[str, Any]]] = {vid: [] for vid in video_ids}
    if not video_ids:
        return result
    cur.execute(
        """
        SELECT vg.video_id, g.id, g.name
        FROM movie_management.video_genres vg
        JOIN movie_management.genres g ON g.id = vg.genre_id
        WHERE vg.video_id = ANY(%s)
        ORDER BY g.sort_order ASC, g.id ASC
        """,
        (list(video_ids),),
    )
    for row in cur.fetchall():
        result[int(row["video_id"])].append({"id": row["id"], "name": row["name"]})
    return result


def replace_genres(cur: PgCursor, video_id: int, genre_ids: Sequence[int]) -> None:
    cur.execute("DELETE FROM movie_management.video_genres WHERE video_id = %s", (video_id,))
    if genre_ids:
        execute_values(
            cur,
            "INSERT INTO movie_management.video_genres (video_id, genre_id) VALUES %s",
            [(video_id, gid) for gid in genre_ids],
        )


# 更新を許す列（PATCH）。列名を SQL に埋め込むため、この一覧にあるものだけを受ける。
_UPDATABLE = (
    "title",
    "description",
    "series_id",
    "episode_number",
    "episode_title",
    "sort_order",
)


def update_fields(cur: PgCursor, user_id: int, video_id: int, fields: dict[str, Any]) -> None:
    columns = [name for name in _UPDATABLE if name in fields]
    assignments = ", ".join(f"{name} = %s" for name in columns)
    if assignments:
        assignments += ", "
    cur.execute(
        f"UPDATE movie_management.videos SET {assignments}updated_at = now() WHERE id = %s AND user_id = %s",
        (*[fields[name] for name in columns], video_id, user_id),
    )


def delete_video(cur: PgCursor, user_id: int, video_id: int) -> bool:
    """物理削除。チャンク・サムネイル・ジャンル関連・再生状態・プレイリスト項目は連鎖して消える。"""
    cur.execute(
        "DELETE FROM movie_management.videos WHERE id = %s AND user_id = %s RETURNING id",
        (video_id, user_id),
    )
    return cur.fetchone() is not None


def _filters(
    user_id: int,
    status: str,
    genre_id: int | None,
    series_id: int | None,
    pattern: str | None,
) -> tuple[str, list[Any]]:
    clauses = ["v.user_id = %s"]
    params: list[Any] = [user_id]
    if status != "all":
        clauses.append("v.status = %s")
        params.append(status)
    if genre_id is not None:
        clauses.append(
            "EXISTS (SELECT 1 FROM movie_management.video_genres vg"
            " WHERE vg.video_id = v.id AND vg.genre_id = %s)"
        )
        params.append(genre_id)
    if series_id is not None:
        clauses.append("v.series_id = %s")
        params.append(series_id)
    if pattern is not None:
        clauses.append("(v.title ILIKE %s OR v.episode_title ILIKE %s)")
        params.extend([pattern, pattern])
    return " AND ".join(clauses), params


def count_videos(
    cur: PgCursor,
    user_id: int,
    status: str,
    genre_id: int | None,
    series_id: int | None,
    pattern: str | None,
) -> int:
    where, params = _filters(user_id, status, genre_id, series_id, pattern)
    cur.execute(f"SELECT count(*) AS n FROM movie_management.videos v WHERE {where}", params)
    return int(cur.fetchone()["n"])


def list_videos(
    cur: PgCursor,
    user_id: int,
    status: str,
    genre_id: int | None,
    series_id: int | None,
    pattern: str | None,
    sort: str,
    order: str,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    where, params = _filters(user_id, status, genre_id, series_id, pattern)
    column = _SORT_COLUMNS[sort]
    direction = "ASC" if order == "asc" else "DESC"
    # 最終再生日時の並びでは、未再生（NULL）を昇順・降順のどちらでも末尾にする
    cur.execute(
        f"""
        {_SUMMARY_SELECT}
        WHERE {where}
        ORDER BY {column} {direction} NULLS LAST, v.id DESC
        LIMIT %s OFFSET %s
        """,
        (user_id, *params, limit, offset),
    )
    return [dict(row) for row in cur.fetchall()]
