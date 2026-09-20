"""DDL の制約（db-design.md）が DB で効いていることを確認する。"""

from __future__ import annotations

import pytest
from psycopg2 import errors

from app.db import get_conn

from conftest import TestUser


def _new_video(cur, user_id: int, **overrides) -> int:
    values = {"title": "t", "duration_ms": 1000, "series_id": None, "episode_number": None, "status": "uploading"}
    values.update(overrides)
    cur.execute(
        """
        INSERT INTO movie_management.videos (user_id, series_id, title, episode_number, duration_ms, status, chunk_count)
        VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
        """,
        (
            user_id,
            values["series_id"],
            values["title"],
            values["episode_number"],
            values["duration_ms"],
            values["status"],
            1 if values["status"] == "ready" else 0,
        ),
    )
    return int(cur.fetchone()["id"])


def test_system_genre_name_is_unique() -> None:
    with pytest.raises(errors.UniqueViolation):
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO movie_management.genres (user_id, name) VALUES (NULL, '洋画')")


def test_episode_number_is_unique_within_series(user: TestUser) -> None:
    with pytest.raises(errors.UniqueViolation):
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO movie_management.series (user_id, title) VALUES (%s, 's') RETURNING id", (user.id,)
            )
            series_id = int(cur.fetchone()["id"])
            _new_video(cur, user.id, series_id=series_id, episode_number=1)
            _new_video(cur, user.id, series_id=series_id, episode_number=1)


def test_standalone_videos_may_share_episode_number(user: TestUser) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        _new_video(cur, user.id, episode_number=1)
        _new_video(cur, user.id, episode_number=1)


def test_chunk_byte_length_must_match_data(user: TestUser) -> None:
    with pytest.raises(errors.CheckViolation):
        with get_conn() as conn, conn.cursor() as cur:
            video_id = _new_video(cur, user.id)
            cur.execute(
                """
                INSERT INTO movie_management.video_chunks
                    (video_id, chunk_index, start_time_ms, end_time_ms, byte_length, data)
                VALUES (%s, 0, 0, 1000, 5, %s)
                """,
                (video_id, b"abc"),
            )


def test_ready_video_needs_chunks(user: TestUser) -> None:
    with pytest.raises(errors.CheckViolation):
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO movie_management.videos (user_id, title, duration_ms, status, chunk_count)
                VALUES (%s, 't', 1000, 'ready', 0)
                """,
                (user.id,),
            )


@pytest.mark.parametrize("duration", [0, 14_400_001])
def test_duration_range(user: TestUser, duration: int) -> None:
    with pytest.raises(errors.CheckViolation):
        with get_conn() as conn, conn.cursor() as cur:
            _new_video(cur, user.id, duration_ms=duration)


def test_deleting_video_cascades_and_nulls_context(user: TestUser) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        video_id = _new_video(cur, user.id)
        cur.execute(
            """
            INSERT INTO movie_management.video_chunks
                (video_id, chunk_index, start_time_ms, end_time_ms, byte_length, data)
            VALUES (%s, 0, 0, 1000, 3, %s)
            """,
            (video_id, b"abc"),
        )
        cur.execute(
            "INSERT INTO movie_management.thumbnails (video_id, data) VALUES (%s, %s)", (video_id, b"x")
        )
        cur.execute(
            "INSERT INTO movie_management.playback_states (user_id, video_id) VALUES (%s, %s)", (user.id, video_id)
        )
        cur.execute(
            "INSERT INTO movie_management.playback_contexts (user_id, last_video_id) VALUES (%s, %s)",
            (user.id, video_id),
        )
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM movie_management.videos WHERE id = %s", (video_id,))
    with get_conn() as conn, conn.cursor() as cur:
        for table in ("video_chunks", "thumbnails", "playback_states"):
            cur.execute(f"SELECT count(*) AS n FROM movie_management.{table} WHERE video_id = %s", (video_id,))
            assert cur.fetchone()["n"] == 0, table
        cur.execute("SELECT last_video_id FROM movie_management.playback_contexts WHERE user_id = %s", (user.id,))
        assert cur.fetchone()["last_video_id"] is None


def test_ddl_is_reapplicable() -> None:
    from pathlib import Path

    sql = (Path(__file__).resolve().parent.parent / "backend" / "sql" / "01_movie_management.sql").read_text(
        encoding="utf-8"
    )
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql)
        cur.execute("SELECT count(*) AS n FROM movie_management.genres WHERE user_id IS NULL")
        assert cur.fetchone()["n"] == 7
