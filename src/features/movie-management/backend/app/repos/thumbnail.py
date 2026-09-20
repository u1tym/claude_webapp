from __future__ import annotations

from typing import Any

from psycopg2.extensions import cursor as PgCursor


def upsert_thumbnail(
    cur: PgCursor,
    video_id: int,
    mime_type: str,
    width: int | None,
    height: int | None,
    data: bytes,
) -> None:
    cur.execute(
        """
        INSERT INTO movie_management.thumbnails (video_id, mime_type, width, height, data)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (video_id) DO UPDATE
        SET mime_type = EXCLUDED.mime_type, width = EXCLUDED.width,
            height = EXCLUDED.height, data = EXCLUDED.data, created_at = now()
        """,
        (video_id, mime_type, width, height, data),
    )


def get_thumbnail(cur: PgCursor, user_id: int, video_id: int) -> dict[str, Any] | None:
    """本人の動画のサムネイル。未登録・他ユーザの動画は None。"""
    cur.execute(
        """
        SELECT t.mime_type, t.data
        FROM movie_management.thumbnails t
        JOIN movie_management.videos v ON v.id = t.video_id
        WHERE t.video_id = %s AND v.user_id = %s
        """,
        (video_id, user_id),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return {"mime_type": row["mime_type"], "data": bytes(row["data"])}
