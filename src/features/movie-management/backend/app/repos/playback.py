from __future__ import annotations

from datetime import datetime
from typing import Any

from psycopg2.extensions import cursor as PgCursor


def get_state(cur: PgCursor, user_id: int, video_id: int) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT position_ms, completed, play_count, last_played_at
        FROM movie_management.playback_states
        WHERE user_id = %s AND video_id = %s
        """,
        (user_id, video_id),
    )
    row = cur.fetchone()
    return dict(row) if row is not None else None


def record_play_start(cur: PgCursor, user_id: int, video_id: int) -> dict[str, Any]:
    """再生の開始を記録する（再生回数 +1、最終再生日時を更新）。位置と視聴完了は変えない。"""
    cur.execute(
        """
        INSERT INTO movie_management.playback_states (user_id, video_id, play_count)
        VALUES (%s, %s, 1)
        ON CONFLICT (user_id, video_id) DO UPDATE
        SET play_count = movie_management.playback_states.play_count + 1,
            last_played_at = now(), updated_at = now()
        RETURNING position_ms, completed, play_count, last_played_at
        """,
        (user_id, video_id),
    )
    return dict(cur.fetchone())


def save_state(
    cur: PgCursor, user_id: int, video_id: int, position_ms: int, completed: bool
) -> datetime:
    """再生位置と視聴完了を保存する（無ければ作る）。再生回数は変えない。"""
    cur.execute(
        """
        INSERT INTO movie_management.playback_states (user_id, video_id, position_ms, completed)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id, video_id) DO UPDATE
        SET position_ms = EXCLUDED.position_ms, completed = EXCLUDED.completed,
            last_played_at = now(), updated_at = now()
        RETURNING last_played_at
        """,
        (user_id, video_id, position_ms, completed),
    )
    return cur.fetchone()["last_played_at"]


def upsert_video_context(cur: PgCursor, user_id: int, video_id: int, position_ms: int) -> None:
    """続きから視聴の「最後に単独で再生した動画」を更新する。プレイリスト側は変えない。"""
    cur.execute(
        """
        INSERT INTO movie_management.playback_contexts
            (user_id, last_video_id, last_video_position_ms, last_video_updated_at, updated_at)
        VALUES (%s, %s, %s, now(), now())
        ON CONFLICT (user_id) DO UPDATE
        SET last_video_id = EXCLUDED.last_video_id,
            last_video_position_ms = EXCLUDED.last_video_position_ms,
            last_video_updated_at = now(), updated_at = now()
        """,
        (user_id, video_id, position_ms),
    )


def upsert_playlist_context(
    cur: PgCursor, user_id: int, playlist_id: int, item_id: int, position_ms: int
) -> None:
    """続きから視聴の「最後に再生したプレイリスト」を更新する。単独再生側は変えない。"""
    cur.execute(
        """
        INSERT INTO movie_management.playback_contexts
            (user_id, last_playlist_id, last_playlist_item_id, last_playlist_position_ms,
             last_playlist_updated_at, updated_at)
        VALUES (%s, %s, %s, %s, now(), now())
        ON CONFLICT (user_id) DO UPDATE
        SET last_playlist_id = EXCLUDED.last_playlist_id,
            last_playlist_item_id = EXCLUDED.last_playlist_item_id,
            last_playlist_position_ms = EXCLUDED.last_playlist_position_ms,
            last_playlist_updated_at = now(), updated_at = now()
        """,
        (user_id, playlist_id, item_id, position_ms),
    )


def get_context(cur: PgCursor, user_id: int) -> dict[str, Any] | None:
    cur.execute("SELECT * FROM movie_management.playback_contexts WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    return dict(row) if row is not None else None


def last_video(cur: PgCursor, user_id: int) -> dict[str, Any] | None:
    """続きから視聴の動画。削除済み・再生できない状態のものは返さない。"""
    cur.execute(
        """
        SELECT v.id AS video_id, v.title, v.duration_ms,
               c.last_video_position_ms AS position_ms, c.last_video_updated_at AS updated_at
        FROM movie_management.playback_contexts c
        JOIN movie_management.videos v ON v.id = c.last_video_id
        WHERE c.user_id = %s AND v.user_id = %s AND v.status = 'ready'
          AND c.last_video_updated_at IS NOT NULL
        """,
        (user_id, user_id),
    )
    row = cur.fetchone()
    return dict(row) if row is not None else None


def last_playlist(cur: PgCursor, user_id: int) -> dict[str, Any] | None:
    """続きから視聴のプレイリスト。削除済み・項目の動画が再生できない状態のものは返さない。"""
    cur.execute(
        """
        SELECT p.id AS playlist_id, p.name AS playlist_name, i.id AS item_id,
               v.id AS video_id, v.title AS video_title, v.duration_ms,
               c.last_playlist_position_ms AS position_ms, c.last_playlist_updated_at AS updated_at
        FROM movie_management.playback_contexts c
        JOIN movie_management.playlists p ON p.id = c.last_playlist_id
        JOIN movie_management.playlist_items i ON i.id = c.last_playlist_item_id AND i.playlist_id = p.id
        JOIN movie_management.videos v ON v.id = i.video_id
        WHERE c.user_id = %s AND p.user_id = %s AND v.user_id = %s AND v.status = 'ready'
          AND c.last_playlist_updated_at IS NOT NULL
        """,
        (user_id, user_id, user_id),
    )
    row = cur.fetchone()
    return dict(row) if row is not None else None


def count_history(cur: PgCursor, user_id: int) -> int:
    cur.execute(
        "SELECT count(*) AS n FROM movie_management.playback_states WHERE user_id = %s", (user_id,)
    )
    return int(cur.fetchone()["n"])


def list_history(cur: PgCursor, user_id: int, limit: int, offset: int) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT v.id AS video_id, v.title, ps.position_ms, ps.completed, v.duration_ms, ps.last_played_at
        FROM movie_management.playback_states ps
        JOIN movie_management.videos v ON v.id = ps.video_id
        WHERE ps.user_id = %s
        ORDER BY ps.last_played_at DESC, ps.video_id DESC
        LIMIT %s OFFSET %s
        """,
        (user_id, limit, offset),
    )
    return [dict(row) for row in cur.fetchall()]


def next_in_series(cur: PgCursor, user_id: int, current: dict[str, Any]) -> dict[str, Any] | None:
    """同一作品で、作品内順序が現在より後ろの「再生可能」な動画のうち最初のもの。

    作品内順序が同じ動画は、話数、識別子の順で前後を決める（一覧の並びと同じ）。
    """
    cur.execute(
        """
        SELECT id, title, episode_number, sort_order, duration_ms, status
        FROM movie_management.videos
        WHERE user_id = %s AND series_id = %s AND status = 'ready'
          AND (sort_order, COALESCE(episode_number, 2147483647), id) > (%s, %s, %s)
        ORDER BY sort_order ASC, COALESCE(episode_number, 2147483647) ASC, id ASC
        LIMIT 1
        """,
        (
            user_id,
            current["series_id"],
            current["sort_order"],
            current["episode_number"] if current["episode_number"] is not None else 2147483647,
            current["id"],
        ),
    )
    row = cur.fetchone()
    return dict(row) if row is not None else None


def next_standalone(cur: PgCursor, user_id: int, current: dict[str, Any]) -> dict[str, Any] | None:
    """作品に属さない「再生可能」な動画のうち、登録日時が現在より新しい最も古いもの。"""
    cur.execute(
        """
        SELECT id, title, episode_number, sort_order, duration_ms, status
        FROM movie_management.videos
        WHERE user_id = %s AND series_id IS NULL AND status = 'ready'
          AND (created_at, id) > (%s, %s)
        ORDER BY created_at ASC, id ASC
        LIMIT 1
        """,
        (user_id, current["created_at"], current["id"]),
    )
    row = cur.fetchone()
    return dict(row) if row is not None else None


def get_video_for_next(cur: PgCursor, user_id: int, video_id: int) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT id, series_id, sort_order, episode_number, created_at
        FROM movie_management.videos
        WHERE id = %s AND user_id = %s
        """,
        (video_id, user_id),
    )
    row = cur.fetchone()
    return dict(row) if row is not None else None
