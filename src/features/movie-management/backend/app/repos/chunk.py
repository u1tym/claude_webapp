from __future__ import annotations

from typing import Any

from psycopg2.extensions import cursor as PgCursor


def insert_chunk(
    cur: PgCursor,
    video_id: int,
    chunk_index: int,
    start_time_ms: int,
    end_time_ms: int,
    data: bytes,
) -> None:
    cur.execute(
        """
        INSERT INTO movie_management.video_chunks
            (video_id, chunk_index, start_time_ms, end_time_ms, byte_length, data)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (video_id, chunk_index, start_time_ms, end_time_ms, len(data), data),
    )


def add_to_video_totals(cur: PgCursor, video_id: int, byte_length: int) -> int:
    """動画のチャンク数とファイルサイズの合計を加算し、加算後のチャンク数を返す。"""
    cur.execute(
        """
        UPDATE movie_management.videos
        SET chunk_count = chunk_count + 1,
            file_size_bytes = file_size_bytes + %s,
            updated_at = now()
        WHERE id = %s
        RETURNING chunk_count
        """,
        (byte_length, video_id),
    )
    return int(cur.fetchone()["chunk_count"])


def stats(cur: PgCursor, video_id: int) -> dict[str, int]:
    """登録済みチャンクの実際の件数・バイト長の合計・最大の番号。"""
    cur.execute(
        """
        SELECT count(*) AS chunk_count,
               COALESCE(sum(byte_length), 0)::bigint AS total_bytes,
               COALESCE(max(chunk_index), -1) AS max_index
        FROM movie_management.video_chunks
        WHERE video_id = %s
        """,
        (video_id,),
    )
    row = cur.fetchone()
    return {
        "chunk_count": int(row["chunk_count"]),
        "total_bytes": int(row["total_bytes"]),
        "max_index": int(row["max_index"]),
    }


def delete_chunks(cur: PgCursor, video_id: int) -> None:
    cur.execute("DELETE FROM movie_management.video_chunks WHERE video_id = %s", (video_id,))


def mark_ready(cur: PgCursor, video_id: int, duration_ms: int, chunk_count: int, total_bytes: int) -> None:
    cur.execute(
        """
        UPDATE movie_management.videos
        SET status = 'ready', duration_ms = %s, chunk_count = %s, file_size_bytes = %s, updated_at = now()
        WHERE id = %s
        """,
        (duration_ms, chunk_count, total_bytes, video_id),
    )


def reset_for_replace(cur: PgCursor, video_id: int, duration_ms: int, mime_type: str) -> None:
    """差し替えの開始。動画を「登録中」に戻し、ファイルに関する値を初期化する。"""
    cur.execute(
        """
        UPDATE movie_management.videos
        SET status = 'uploading', chunk_count = 0, file_size_bytes = 0,
            duration_ms = %s, mime_type = %s, updated_at = now()
        WHERE id = %s
        """,
        (duration_ms, mime_type, video_id),
    )
    # 再生位置と視聴完了を先頭に戻す（この動画に関するものだけ）
    cur.execute(
        """
        UPDATE movie_management.playback_states
        SET position_ms = 0, completed = false, updated_at = now()
        WHERE video_id = %s
        """,
        (video_id,),
    )
    cur.execute(
        "UPDATE movie_management.playback_contexts SET last_video_position_ms = 0 WHERE last_video_id = %s",
        (video_id,),
    )
    cur.execute(
        """
        UPDATE movie_management.playback_contexts
        SET last_playlist_position_ms = 0
        WHERE last_playlist_item_id IN (
            SELECT id FROM movie_management.playlist_items WHERE video_id = %s)
        """,
        (video_id,),
    )


def layout(cur: PgCursor, video_id: int) -> list[tuple[int, int]]:
    """(チャンク番号, バイト長) を番号順に返す。データ本体は読まない。"""
    cur.execute(
        """
        SELECT chunk_index, byte_length
        FROM movie_management.video_chunks
        WHERE video_id = %s
        ORDER BY chunk_index ASC
        """,
        (video_id,),
    )
    return [(int(row["chunk_index"]), int(row["byte_length"])) for row in cur.fetchall()]


def find_chunk_at(cur: PgCursor, video_id: int, position_ms: int) -> dict[str, Any] | None:
    """再生位置（ミリ秒）に対応するチャンク（開始が位置以下で最も後ろのもの）。"""
    cur.execute(
        """
        SELECT chunk_index, start_time_ms, end_time_ms, byte_length
        FROM movie_management.video_chunks
        WHERE video_id = %s AND start_time_ms <= %s
        ORDER BY start_time_ms DESC
        LIMIT 1
        """,
        (video_id, position_ms),
    )
    row = cur.fetchone()
    return dict(row) if row is not None else None
