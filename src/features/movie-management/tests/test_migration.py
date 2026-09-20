"""移行プログラム（scripts/migrate_from_movie.py）のテスト。

移行元は、サンプルの構造を再現した一時的な DB（管理者で作成し、テスト後に削除）、
移行先は開発用 DB（backend/.env）を使う。管理者で接続できないときは、このファイルのテストを飛ばす。
"""

from __future__ import annotations

import io
import os
import sys
import tracemalloc
import uuid
from collections.abc import Callable, Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2
import pytest
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2.extras import RealDictCursor

from app.config import load_config
from app.db import connect, get_conn

from conftest import TestUser, log_text, make_video_file

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend" / "scripts"))
import migrate_from_movie as mig  # noqa: E402

ADMIN = {
    "user": os.environ.get("PG_ADMIN_USER", "postgres"),
    "password": os.environ.get("PG_ADMIN_PASSWORD", "postgres"),
}
FIXTURE_SQL = Path(__file__).resolve().parent / "fixtures" / "source_movie.sql"
T0 = datetime(2020, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
T1 = datetime(2021, 6, 7, 8, 9, 10, tzinfo=timezone.utc)


def _admin_connect(dbname: str, dict_rows: bool = False) -> psycopg2.extensions.connection:
    cfg = load_config()
    return psycopg2.connect(
        host=cfg.db_server, port=cfg.db_port, dbname=dbname,
        cursor_factory=RealDictCursor if dict_rows else None, **ADMIN,
    )


@pytest.fixture(scope="module")
def source_db_name() -> Iterator[str]:
    name = f"mm_src_{uuid.uuid4().hex[:10]}"
    try:
        admin = _admin_connect("postgres")
    except psycopg2.Error:
        pytest.skip("管理者で DB に接続できないため、移行のテストを飛ばします")
    admin.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    with admin.cursor() as cur:
        cur.execute(f'CREATE DATABASE "{name}"')
    conn = _admin_connect(name)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(FIXTURE_SQL.read_text(encoding="utf-8"))
    conn.close()
    yield name
    with admin.cursor() as cur:
        cur.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s", (name,))
        cur.execute(f'DROP DATABASE IF EXISTS "{name}"')
    admin.close()


class Source:
    """移行元 DB へテストデータを入れる。"""

    def __init__(self, conn: psycopg2.extensions.connection) -> None:
        self.conn = conn

    def _one(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()[0]

    def _exec(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        with self.conn.cursor() as cur:
            cur.execute(sql, params)

    def account(self, username: str) -> int:
        return self._one("INSERT INTO public.accounts (username) VALUES (%s) RETURNING id", (username,))

    def genre(self, name: str, aid: int | None = None, sort_order: int = 0) -> int:
        return self._one(
            "INSERT INTO movie.genre (aid, name, sort_order, created_at, updated_at) VALUES (%s,%s,%s,%s,%s) RETURNING genre_id",
            (aid, name, sort_order, T0, T1),
        )

    def series(self, aid: int, title: str, description: str | None = None) -> int:
        return self._one(
            "INSERT INTO movie.series (aid, title, description, created_at, updated_at) VALUES (%s,%s,%s,%s,%s) RETURNING series_id",
            (aid, title, description, T0, T1),
        )

    def video(
        self,
        aid: int,
        title: str,
        data: bytes | None = None,
        *,
        chunk_size: int = 1000,
        duration_ms: int = 10_000,
        status: str = "ready",
        series_id: int | None = None,
        episode_number: int | None = None,
        episode_title: str | None = None,
        sort_order: int = 0,
        genres: tuple[int, ...] = (),
        thumbnail: bytes | None = None,
        created_at: datetime = T0,
        declared_length: int | None = None,
    ) -> int:
        data = make_video_file(2500) if data is None else data
        total = max(1, -(-len(data) // chunk_size)) if data else 0
        video_id = self._one(
            """
            INSERT INTO movie.video (aid, series_id, title, description, episode_number, episode_title,
                sort_order, duration_ms, mime_type, file_size_bytes, chunk_count, status, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'video/mp4',%s,%s,%s,%s,%s) RETURNING video_id
            """,
            (aid, series_id, title, f"{title}の説明", episode_number, episode_title, sort_order,
             duration_ms, len(data), total, status, created_at, T1),
        )
        segment = -(-duration_ms // max(total, 1))
        for index in range(total):
            part = data[index * chunk_size : (index + 1) * chunk_size]
            self._exec(
                """
                INSERT INTO movie.video_chunk (video_id, chunk_index, start_time_ms, end_time_ms, byte_length, data, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                (video_id, index, index * segment, (index + 1) * segment,
                 declared_length if declared_length is not None else len(part), part, T0),
            )
        for genre_id in genres:
            self._exec("INSERT INTO movie.video_genre (video_id, genre_id, created_at) VALUES (%s,%s,%s)", (video_id, genre_id, T0))
        if thumbnail is not None:
            self._exec(
                "INSERT INTO movie.thumbnail (video_id, mime_type, width, height, data, created_at) VALUES (%s,'image/jpeg',320,180,%s,%s)",
                (video_id, thumbnail, T0),
            )
        return video_id

    def state(self, aid: int, video_id: int, position_ms: int, *, completed: bool = False, play_count: int = 3) -> None:
        self._exec(
            """
            INSERT INTO movie.playback_state (aid, video_id, position_ms, completed, play_count, last_played_at, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (aid, video_id, position_ms, completed, play_count, T1, T0, T1),
        )

    def playlist(self, aid: int, name: str, video_ids: list[int]) -> tuple[int, list[int]]:
        playlist_id = self._one(
            "INSERT INTO movie.playlist (aid, name, description, created_at, updated_at) VALUES (%s,%s,%s,%s,%s) RETURNING playlist_id",
            (aid, name, f"{name}の説明", T0, T1),
        )
        items = [
            self._one(
                "INSERT INTO movie.playlist_item (playlist_id, video_id, sort_order, created_at) VALUES (%s,%s,%s,%s) RETURNING playlist_item_id",
                (playlist_id, video_id, 10 * (index + 1), T0),  # 移行元の並びは飛び番でもよい
            )
            for index, video_id in enumerate(video_ids)
        ]
        return playlist_id, items

    def context(self, aid: int, **fields: Any) -> None:
        columns = ["aid", *fields]
        self._exec(
            f"INSERT INTO movie.playback_context ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(columns))})",
            (aid, *fields.values()),
        )


@pytest.fixture()
def src(source_db_name: str) -> Iterator[Source]:
    conn = _admin_connect(source_db_name)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "TRUNCATE movie.playback_context, movie.playback_state, movie.playlist_item, movie.playlist, "
            "movie.thumbnail, movie.video_chunk, movie.video_genre, movie.video, movie.series, movie.genre, "
            "public.accounts RESTART IDENTITY CASCADE"
        )
    yield Source(conn)
    conn.close()


@pytest.fixture(autouse=True)
def keep_test_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    """main() がログの出力先を backend/log へ切り替えないようにする（テスト用の出力先を使い続ける）。"""
    monkeypatch.setattr(mig, "setup_logging", lambda: None)


@pytest.fixture(autouse=True)
def cleanup_system_genres() -> Iterator[None]:
    yield
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM movie_management.genres WHERE user_id IS NULL AND name LIKE 'mmtest_%'")


class Runner:
    def __init__(self, db_name: str) -> None:
        self.db_name = db_name

    def run(self, *, dry_run: bool = False, usernames: list[str] | None = None) -> tuple[mig.Report, str]:
        source = _admin_connect(self.db_name, dict_rows=True)
        source.set_session(readonly=True)
        target = connect()
        out = io.StringIO()
        try:
            report = mig.run(source, target, mig.Options(dry_run=dry_run, usernames=usernames), out)
        finally:
            source.close()
            target.close()
        return report, out.getvalue()


@pytest.fixture()
def migrate(source_db_name: str) -> Runner:
    return Runner(source_db_name)


def _rows(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def _videos_of(user: TestUser) -> list[dict[str, Any]]:
    return _rows("SELECT * FROM movie_management.videos WHERE user_id = %s ORDER BY id", (user.id,))


# ---- ユーザの対応付け --------------------------------------------------------


def test_only_matching_active_users_are_migrated(
    src: Source, migrate: Runner, make_user: Callable[..., TestUser]
) -> None:
    matched = make_user()
    deleted = make_user(deleted=True)
    ghost = f"mm_ghost_{uuid.uuid4().hex[:8]}"
    for name in (matched.username, deleted.username, ghost):
        aid = src.account(name)
        src.video(aid, f"動画-{name[-4:]}")
        src.series(aid, "作品")
    report, out = migrate.run()
    assert report.count("video", "migrated") == 1
    assert len(_videos_of(matched)) == 1
    assert _videos_of(deleted) == []
    excluded = report.details[("user", "excluded")]
    assert any(ghost in line and "動画 1 件" in line for line in excluded)
    assert any(deleted.username in line for line in excluded)
    assert not any(matched.username in line for line in excluded)
    assert "移行対象のユーザ: 1 人" in out


def test_username_option_limits_users(src: Source, migrate: Runner, make_user: Callable[..., TestUser]) -> None:
    first, second = make_user(), make_user()
    for user in (first, second):
        src.video(src.account(user.username), "動画")
    report, out = migrate.run(usernames=[first.username, "mm_missing_user"])
    assert report.count("video", "migrated") == 1
    assert len(_videos_of(first)) == 1 and _videos_of(second) == []
    assert "mm_missing_user" in out  # 移行元に無い指定は警告する
    assert not report.details.get(("user", "excluded"))  # 指定外のユーザは対象外として数えない


# ---- 動画 -------------------------------------------------------------------


def test_video_is_copied_with_all_values(src: Source, migrate: Runner, user: TestUser) -> None:
    aid = src.account(user.username)
    data = make_video_file(3500)
    series_id = src.series(aid, "作品A", "作品の説明")
    genre_id = src.genre("mmtest_own", aid=aid, sort_order=5)
    src.video(
        aid, "第2話", data, series_id=series_id, episode_number=2, episode_title="展開", sort_order=20,
        genres=(genre_id,), thumbnail=b"jpeg-bytes", duration_ms=8000,
    )
    report, _ = migrate.run()
    assert report.failures == 0
    (video,) = _videos_of(user)
    assert (video["title"], video["description"], video["episode_number"], video["episode_title"]) == (
        "第2話", "第2話の説明", 2, "展開",
    )
    assert (video["sort_order"], video["duration_ms"], video["mime_type"], video["status"]) == (20, 8000, "video/mp4", "ready")
    assert (video["chunk_count"], video["file_size_bytes"]) == (4, 3500)
    assert (video["created_at"], video["updated_at"]) == (T0, T1)  # 移行元の日時を引き継ぐ
    # チャンクの分割とバイト列が同じ
    chunks = _rows(
        "SELECT chunk_index, start_time_ms, end_time_ms, byte_length, data FROM movie_management.video_chunks "
        "WHERE video_id = %s ORDER BY chunk_index",
        (video["id"],),
    )
    assert [c["byte_length"] for c in chunks] == [1000, 1000, 1000, 500]
    assert [(c["start_time_ms"], c["end_time_ms"]) for c in chunks] == [(0, 2000), (2000, 4000), (4000, 6000), (6000, 8000)]
    assert b"".join(bytes(c["data"]) for c in chunks) == data
    # 再生画面と同じ経路（範囲配信）でも取り出せる
    assert user.client.get(f"/videos/{video['id']}/stream").content == data
    # 作品・ジャンル・サムネイル
    detail = user.client.get(f"/videos/{video['id']}").json()
    assert detail["series_title"] == "作品A"
    assert [g["name"] for g in detail["genres"]] == ["mmtest_own"]
    assert user.client.get(f"/videos/{video['id']}/thumbnail").content == b"jpeg-bytes"
    assert report.count("thumbnail", "migrated") == 1
    (series,) = _rows("SELECT * FROM movie_management.series WHERE user_id = %s", (user.id,))
    assert (series["title"], series["description"], series["created_at"], series["updated_at"]) == ("作品A", "作品の説明", T0, T1)


def test_only_ready_videos_are_migrated(src: Source, migrate: Runner, user: TestUser) -> None:
    aid = src.account(user.username)
    src.video(aid, "再生可能")
    src.video(aid, "登録中", status="uploading")
    src.video(aid, "エラー", status="error")
    report, _ = migrate.run()
    assert [v["title"] for v in _videos_of(user)] == ["再生可能"]
    assert report.count("video", "excluded") == 2
    assert any("登録中" in d or "uploading" in d for d in report.details[("video", "excluded")])


def test_failed_video_leaves_nothing_and_next_one_continues(src: Source, migrate: Runner, user: TestUser) -> None:
    aid = src.account(user.username)
    src.video(aid, "壊れた動画", make_video_file(2500), declared_length=999)  # 宣言した長さと実データが違う
    src.video(aid, "チャンクなし", b"")
    src.video(aid, "正常な動画", make_video_file(1500, seed=3))
    report, _ = migrate.run()
    assert [v["title"] for v in _videos_of(user)] == ["正常な動画"]
    assert report.count("video", "failed") == 2
    assert report.count("video", "migrated") == 1
    assert report.failures == 2
    failed = "\n".join(report.details[("video", "failed")])
    assert "壊れた動画" in failed and "チャンクなし" in failed and "移行元にチャンクがありません" in failed
    # 途中まで書いたチャンクも残らない
    assert _rows(
        "SELECT count(*) AS n FROM movie_management.video_chunks c JOIN movie_management.videos v ON v.id = c.video_id "
        "WHERE v.user_id = %s AND v.title = '壊れた動画'",
        (user.id,),
    )[0]["n"] == 0


def test_rerun_skips_already_migrated(src: Source, migrate: Runner, user: TestUser) -> None:
    aid = src.account(user.username)
    series_id = src.series(aid, "作品")
    genre_id = src.genre("mmtest_g", aid=aid)
    video_id = src.video(aid, "動画A", series_id=series_id, genres=(genre_id,), thumbnail=b"t")
    src.video(aid, "動画B", make_video_file(1800, seed=9))
    src.state(aid, video_id, 1234)
    src.playlist(aid, "リスト", [video_id])
    first, _ = migrate.run()
    assert first.count("video", "migrated") == 2
    before = _videos_of(user)
    second, _ = migrate.run()
    assert second.count("video", "migrated") == 0
    assert second.count("video", "skipped") == 2
    assert second.count("series", "skipped") == 1 and second.count("series", "migrated") == 0
    assert second.count("genre", "skipped") == 1 and second.count("genre", "migrated") == 0
    assert second.count("playback_state", "skipped") == 1
    assert second.count("playlist", "skipped") == 1
    assert second.failures == 0
    assert _videos_of(user) == before  # 二重に増えない
    assert len(_rows("SELECT id FROM movie_management.series WHERE user_id = %s", (user.id,))) == 1
    assert len(_rows("SELECT id FROM movie_management.playlists WHERE user_id = %s", (user.id,))) == 1


def test_resume_after_partial_failure(src: Source, migrate: Runner, user: TestUser) -> None:
    aid = src.account(user.username)
    src.video(aid, "先の動画", make_video_file(1200, seed=1))
    bad = src.video(aid, "途中で壊れる", make_video_file(2200, seed=2), declared_length=1)
    report, _ = migrate.run()
    assert (report.count("video", "migrated"), report.count("video", "failed")) == (1, 1)
    # 原因（移行元のデータ）を直して再実行すると、残りだけが移行される
    with src.conn.cursor() as cur:
        cur.execute("UPDATE movie.video_chunk SET byte_length = octet_length(data) WHERE video_id = %s", (bad,))
    again, _ = migrate.run()
    assert (again.count("video", "migrated"), again.count("video", "skipped"), again.failures) == (1, 1, 0)
    assert sorted(v["title"] for v in _videos_of(user)) == ["先の動画", "途中で壊れる"]


def test_same_title_videos_are_migrated_one_to_one(src: Source, migrate: Runner, user: TestUser) -> None:
    aid = src.account(user.username)
    same = make_video_file(1000, seed=5)
    src.video(aid, "同名", same)
    src.video(aid, "同名", same)  # タイトル・サイズ・長さが同じ動画が 2 件ある
    migrate.run()
    assert len(_videos_of(user)) == 2
    again, _ = migrate.run()
    assert (again.count("video", "skipped"), again.count("video", "migrated")) == (2, 0)
    assert len(_videos_of(user)) == 2


def test_dry_run_writes_nothing(src: Source, migrate: Runner, user: TestUser) -> None:
    aid = src.account(user.username)
    series_id = src.series(aid, "作品")
    new_genre = src.genre("mmtest_dryrun_system")
    own = src.genre("mmtest_dryrun_own", aid=aid)
    video_id = src.video(aid, "動画", series_id=series_id, genres=(new_genre, own), thumbnail=b"t")
    src.state(aid, video_id, 500)
    src.playlist(aid, "リスト", [video_id])
    src.context(aid, last_video_id=video_id, last_video_position_ms=500, last_video_updated_at=T1)
    report, out = migrate.run(dry_run=True)
    assert report.dry_run
    assert report.count("video", "migrated") == 1  # 移行予定
    assert report.count("playlist", "migrated") == 1 and report.count("playback_context", "migrated") == 1
    assert _videos_of(user) == []
    assert _rows("SELECT id FROM movie_management.series WHERE user_id = %s", (user.id,)) == []
    assert _rows("SELECT id FROM movie_management.playlists WHERE user_id = %s", (user.id,)) == []
    assert _rows("SELECT user_id FROM movie_management.playback_contexts WHERE user_id = %s", (user.id,)) == []
    assert _rows("SELECT id FROM movie_management.genres WHERE name LIKE %s", ("mmtest_dryrun%",)) == []
    text = io.StringIO()
    report.print(text)
    assert "ドライラン" in text.getvalue() and "移行予定" in text.getvalue()
    assert "動画" in out


def test_large_video_is_streamed_not_loaded_at_once(src: Source, migrate: Runner, user: TestUser) -> None:
    aid = src.account(user.username)
    chunk = 4 * 1024 * 1024
    total = 16 * chunk  # 64 MiB
    data = make_video_file(chunk, seed=11)
    video_id = src.video(aid, "大きい動画", data * 16, chunk_size=chunk, duration_ms=3_600_000)
    tracemalloc.start()
    try:
        report, _ = migrate.run()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert report.failures == 0
    assert peak < total * 0.6, f"移行中のメモリが大きすぎます: {peak / 1024 / 1024:.1f} MiB"
    (video,) = _videos_of(user)
    assert (video["chunk_count"], video["file_size_bytes"]) == (16, total)
    source_hashes = _hashes(src.conn, "movie.video_chunk", video_id)
    target_hashes = _hashes_target(video["id"])
    assert source_hashes == target_hashes


def _hashes(conn: Any, table: str, video_id: int) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(f"SELECT md5(data) FROM {table} WHERE video_id = %s ORDER BY chunk_index", (video_id,))
        return [row[0] for row in cur.fetchall()]


def _hashes_target(video_id: int) -> list[str]:
    return [
        r["h"]
        for r in _rows(
            "SELECT md5(data) AS h FROM movie_management.video_chunks WHERE video_id = %s ORDER BY chunk_index", (video_id,)
        )
    ]


# ---- ジャンル ---------------------------------------------------------------


def test_system_genres_are_matched_by_name_or_added(src: Source, migrate: Runner, user: TestUser) -> None:
    aid = src.account(user.username)
    existing = src.genre("洋画")
    added = src.genre("mmtest_new_system")
    src.video(aid, "動画", genres=(existing, added))
    report, _ = migrate.run()
    assert report.count("genre", "skipped") == 1 and report.count("genre", "migrated") == 1
    detail = user.client.get(f"/videos/{_videos_of(user)[0]['id']}").json()
    assert {g["name"] for g in detail["genres"]} == {"洋画", "mmtest_new_system"}
    system = _rows("SELECT id FROM movie_management.genres WHERE user_id IS NULL AND name = '洋画'")
    assert len(system) == 1  # 共通ジャンルは増えない
    added_row = _rows("SELECT sort_order FROM movie_management.genres WHERE user_id IS NULL AND name = 'mmtest_new_system'")
    assert len(added_row) == 1


def test_user_genres_match_existing_same_name(src: Source, migrate: Runner, user: TestUser) -> None:
    aid = src.account(user.username)
    user.client.post("/genres", json={"name": "mmtest_same", "sort_order": 7})
    same = src.genre("mmtest_same", aid=aid, sort_order=1)
    other = src.genre("mmtest_other", aid=aid, sort_order=2)
    src.video(aid, "動画", genres=(same, other))
    report, _ = migrate.run()
    assert (report.count("genre", "skipped"), report.count("genre", "migrated")) == (1, 1)
    own = _rows("SELECT name, sort_order FROM movie_management.genres WHERE user_id = %s ORDER BY name", (user.id,))
    assert [(g["name"], g["sort_order"]) for g in own] == [("mmtest_other", 2), ("mmtest_same", 7)]


# ---- 再生状態・プレイリスト・続きから視聴 ------------------------------------


def test_playback_state_is_migrated_but_never_overwritten(src: Source, migrate: Runner, user: TestUser) -> None:
    aid = src.account(user.username)
    a = src.video(aid, "A")
    b = src.video(aid, "B", make_video_file(1500, seed=4))
    src.video(aid, "登録中", status="uploading")
    src.state(aid, a, 4000, completed=True, play_count=5)
    src.state(aid, b, 1000)
    report, _ = migrate.run()
    assert report.count("playback_state", "migrated") == 2
    states = {r["title"]: r for r in _rows(
        "SELECT v.title, ps.* FROM movie_management.playback_states ps JOIN movie_management.videos v ON v.id = ps.video_id "
        "WHERE ps.user_id = %s", (user.id,))}
    assert (states["A"]["position_ms"], states["A"]["completed"], states["A"]["play_count"]) == (4000, True, 5)
    assert (states["A"]["last_played_at"], states["A"]["created_at"], states["A"]["updated_at"]) == (T1, T0, T1)
    # 移行先で視聴が進んだ後に再実行しても、上書きしない
    user.client.put(f"/videos/{states['A']['video_id']}/playback/state", json={"position_ms": 9000, "completed": False})
    again, _ = migrate.run()
    assert again.count("playback_state", "skipped") == 2
    assert user.client.get(f"/videos/{states['A']['video_id']}").json()["position_ms"] == 9000


def test_state_of_unmigrated_video_is_excluded(src: Source, migrate: Runner, user: TestUser) -> None:
    aid = src.account(user.username)
    uploading = src.video(aid, "登録中", status="uploading")
    src.state(aid, uploading, 10)
    report, _ = migrate.run()
    assert (report.count("playback_state", "excluded"), report.count("playback_state", "migrated")) == (1, 0)


def test_playlists_keep_order_and_drop_unmigrated_items(src: Source, migrate: Runner, user: TestUser) -> None:
    aid = src.account(user.username)
    a = src.video(aid, "A")
    b = src.video(aid, "B", make_video_file(1500, seed=4))
    uploading = src.video(aid, "登録中", status="uploading")
    src.playlist(aid, "リスト", [b, uploading, a, b])
    src.playlist(aid, "空", [])
    report, _ = migrate.run()
    assert (report.count("playlist", "migrated"), report.count("playlist_item", "migrated")) == (2, 3)
    assert report.count("playlist_item", "excluded") == 1
    assert any("リスト" in d for d in report.details[("playlist_item", "excluded")])
    playlists = user.client.get("/playlists").json()["items"]
    by_name = {p["name"]: p for p in playlists}
    assert by_name["リスト"]["item_count"] == 3 and by_name["空"]["item_count"] == 0
    detail = user.client.get(f"/playlists/{by_name['リスト']['id']}").json()
    assert [i["title"] for i in detail["items"]] == ["B", "A", "B"]
    assert [i["sort_order"] for i in detail["items"]] == [0, 1, 2]  # 飛び番は詰め直す
    row = _rows("SELECT description, created_at, updated_at FROM movie_management.playlists WHERE id = %s", (by_name["リスト"]["id"],))[0]
    assert (row["description"], row["created_at"], row["updated_at"]) == ("リストの説明", T0, T1)


def test_playback_context_is_mapped_and_partial(src: Source, migrate: Runner, user: TestUser) -> None:
    aid = src.account(user.username)
    a = src.video(aid, "A")
    b = src.video(aid, "B", make_video_file(1500, seed=4))
    playlist_id, items = src.playlist(aid, "リスト", [a, b])
    src.context(
        aid, last_video_id=a, last_video_position_ms=1500, last_video_updated_at=T1,
        last_playlist_id=playlist_id, last_playlist_item_id=items[1], last_playlist_position_ms=2500,
        last_playlist_updated_at=T0,
    )
    report, _ = migrate.run()
    assert report.count("playback_context", "migrated") == 1
    last = user.client.get("/playback/last").json()
    assert (last["video"]["title"], last["video"]["position_ms"]) == ("A", 1500)
    assert (last["playlist"]["playlist_name"], last["playlist"]["video_title"], last["playlist"]["position_ms"]) == (
        "リスト", "B", 2500,
    )
    ctx = _rows("SELECT * FROM movie_management.playback_contexts WHERE user_id = %s", (user.id,))[0]
    assert (ctx["last_video_updated_at"], ctx["last_playlist_updated_at"]) == (T1, T0)
    # 再実行しても上書きしない
    again, _ = migrate.run()
    assert again.count("playback_context", "skipped") == 1


def test_playback_context_pointing_to_unmigrated_targets_is_emptied(src: Source, migrate: Runner, user: TestUser) -> None:
    aid = src.account(user.username)
    a = src.video(aid, "A")
    uploading = src.video(aid, "登録中", status="uploading")
    playlist_id, items = src.playlist(aid, "リスト", [uploading])
    src.context(
        aid, last_video_id=a, last_video_position_ms=100, last_video_updated_at=T1,
        last_playlist_id=playlist_id, last_playlist_item_id=items[0], last_playlist_position_ms=50,
        last_playlist_updated_at=T1,
    )
    report, _ = migrate.run()
    assert report.failures == 0
    ctx = _rows("SELECT * FROM movie_management.playback_contexts WHERE user_id = %s", (user.id,))[0]
    assert ctx["last_video_id"] is not None
    assert (ctx["last_playlist_id"], ctx["last_playlist_item_id"], ctx["last_playlist_position_ms"]) == (None, None, 0)
    assert ctx["last_playlist_updated_at"] is None


def test_context_with_nothing_to_point_to_is_excluded(src: Source, migrate: Runner, user: TestUser) -> None:
    aid = src.account(user.username)
    uploading = src.video(aid, "登録中", status="uploading")
    src.context(aid, last_video_id=uploading, last_video_position_ms=10, last_video_updated_at=T1)
    report, _ = migrate.run()
    assert report.count("playback_context", "excluded") == 1
    assert _rows("SELECT 1 FROM movie_management.playback_contexts WHERE user_id = %s", (user.id,)) == []


# ---- 接続・終了コード・ログ ---------------------------------------------------


def test_source_is_never_modified(src: Source, migrate: Runner, user: TestUser) -> None:
    aid = src.account(user.username)
    src.video(aid, "動画", thumbnail=b"t")
    src.playlist(aid, "リスト", [1])
    snapshot = _source_snapshot(src)
    migrate.run()
    migrate.run(dry_run=True)
    assert _source_snapshot(src) == snapshot


def _source_snapshot(src: Source) -> dict[str, int]:
    tables = ["public.accounts", "movie.genre", "movie.series", "movie.video", "movie.video_chunk", "movie.thumbnail",
              "movie.playback_state", "movie.playlist", "movie.playlist_item", "movie.playback_context", "movie.video_genre"]
    with src.conn.cursor() as cur:
        result = {}
        for table in tables:
            cur.execute(f"SELECT count(*) FROM {table}")
            result[table] = cur.fetchone()[0]
        return result


def test_source_connection_is_read_only(source_db_name: str) -> None:
    args = mig._parse_args(["--host", "localhost", "--dbname", source_db_name, "--user", ADMIN["user"],
                            "--password", ADMIN["password"]])[0]
    conn = mig.open_source(args)
    try:
        with conn.cursor() as cur:
            with pytest.raises(psycopg2.errors.ReadOnlySqlTransaction):
                cur.execute("INSERT INTO public.accounts (username) VALUES ('x')")
    finally:
        conn.close()


def test_main_reports_source_connection_failure(capsys: pytest.CaptureFixture[str], log_dir: Path) -> None:
    code = mig.main(["--host", "127.0.0.1", "--port", "1", "--dbname", "nope", "--user", "u", "--password", "secret-pass-xyz"])
    err = capsys.readouterr().err
    assert code == 2
    assert "移行元DB" in err and "移行先DB" not in err
    assert "secret-pass-xyz" not in err
    assert "secret-pass-xyz" not in log_text(log_dir)


def test_main_reports_target_connection_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], source_db_name: str, log_dir: Path
) -> None:
    def broken() -> Any:
        raise psycopg2.OperationalError("connection refused")

    monkeypatch.setattr(mig, "connect_target", broken)
    code = mig.main(["--host", "localhost", "--dbname", source_db_name, "--user", ADMIN["user"], "--password", ADMIN["password"]])
    err = capsys.readouterr().err
    assert code == 2
    assert "移行先DB" in err
    assert ADMIN["password"] not in err


def test_main_exit_code_and_report(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
    src: Source, source_db_name: str, user: TestUser, log_dir: Path,
) -> None:
    aid = src.account(user.username)
    src.video(aid, "正常")
    argv = ["--host", "localhost", "--dbname", source_db_name, "--user", ADMIN["user"],
            "--password", ADMIN["password"], "--username", user.username]
    assert mig.main(argv) == 0
    err = capsys.readouterr().err
    assert "動画: 移行 1 / スキップ 0 / 対象外 0 / 失敗 0" in err
    assert "[1/1]" in err
    assert ADMIN["password"] not in err
    assert "移行開始" in log_text(log_dir) and "移行終了" in log_text(log_dir)
    assert ADMIN["password"] not in log_text(log_dir)
    src.video(aid, "壊れた", make_video_file(2000), declared_length=1)
    assert mig.main(argv) == 1  # 失敗があれば 0 以外
    err = capsys.readouterr().err
    assert "失敗 1" in err and "壊れた" in err
    assert "動画: 移行 0 / スキップ 1 / 対象外 0 / 失敗 1" in err
