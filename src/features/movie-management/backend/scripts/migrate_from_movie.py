"""別サーバで稼働していた動画視聴サービス（sample/movie）の DB から、本機能の DB へデータを移行する。

移行元 DB と移行先 DB の両方へ同時に接続し、移行元から読んだデータを直接移行先へ書き込む。
ファイルへのエクスポート・インポートはしない。移行元へは読み取りしか行わない。

使い方（backend で venv を有効化してから）:
    python scripts/migrate_from_movie.py --host <移行元ホスト> --dbname <移行元DB名> \\
        --user <移行元ユーザ> --password <移行元パスワード> [--dry-run] [--username <名前> ...]

移行先の接続情報は backend/.env を使う。移行元の接続情報は環境変数でも指定できる（引数が優先）:
    MOVIE_DB_HOST, MOVIE_DB_PORT, MOVIE_DB_NAME, MOVIE_DB_USER, MOVIE_DB_PASSWORD

詳細は scripts/README.md。
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import psycopg2  # noqa: E402
from psycopg2.extensions import connection as PgConnection  # noqa: E402
from psycopg2.extras import RealDictCursor  # noqa: E402

from app.db import connect as connect_target  # noqa: E402
from app.logger import setup_logging, write  # noqa: E402

SRC = "movie"  # 移行元のスキーマ名
DST = "movie_management"  # 移行先のスキーマ名

KINDS = (
    ("user", "ユーザ（対応付けできない移行元アカウント）"),
    ("video", "動画"),
    ("thumbnail", "サムネイル"),
    ("genre", "ジャンル"),
    ("video_genre", "動画とジャンルの関連"),
    ("series", "作品"),
    ("playback_state", "再生状態"),
    ("playlist", "プレイリスト"),
    ("playlist_item", "プレイリストの項目"),
    ("playback_context", "続きから視聴"),
)
STATUSES = (("migrated", "移行"), ("skipped", "スキップ"), ("excluded", "対象外"), ("failed", "失敗"))


class MigrationError(Exception):
    """1 件の移行に失敗した理由（内部理由。結果の一覧とログに出す）。"""


# ---- 結果の記録 -----------------------------------------------------------


@dataclass
class Report:
    dry_run: bool = False
    counts: dict[str, Counter[str]] = field(default_factory=lambda: defaultdict(Counter))
    details: dict[tuple[str, str], list[str]] = field(default_factory=lambda: defaultdict(list))

    def add(self, kind: str, status: str, detail: str | None = None) -> None:
        self.counts[kind][status] += 1
        if detail is not None and status != "migrated":
            self.details[(kind, status)].append(detail)

    def count(self, kind: str, status: str) -> int:
        return self.counts[kind][status]

    @property
    def failures(self) -> int:
        return sum(counter["failed"] for counter in self.counts.values())

    def print(self, out: TextIO) -> None:
        verb = "移行予定" if self.dry_run else "移行"
        print("", file=out)
        print("===== 結果" + ("（ドライラン: 書き込みは行っていません）" if self.dry_run else "") + " =====", file=out)
        for kind, label in KINDS:
            counter = self.counts.get(kind)
            if not counter:
                continue
            parts = [f"{verb if key == 'migrated' else name} {counter[key]}" for key, name in STATUSES]
            print(f"{label}: " + " / ".join(parts), file=out)
            for key, name in STATUSES:
                for detail in self.details.get((kind, key), []):
                    print(f"    [{name}] {detail}", file=out)
        print("", file=out)
        if self.failures:
            print(f"失敗が {self.failures} 件あります。内容を確認し、再実行してください（移行済みは自動でスキップされます）。", file=out)


@dataclass(frozen=True)
class Options:
    dry_run: bool = False
    usernames: Sequence[str] | None = None


@dataclass
class Context:
    """1 回の実行の状態。移行元の識別子から、移行先の識別子への対応を持つ。"""

    src: PgConnection
    dst: PgConnection
    options: Options
    report: Report
    out: TextIO
    genre_map: dict[int, int] = field(default_factory=dict)
    series_map: dict[int, int] = field(default_factory=dict)
    video_map: dict[int, int] = field(default_factory=dict)
    playlist_map: dict[int, int] = field(default_factory=dict)
    item_map: dict[int, int] = field(default_factory=dict)
    _next_placeholder: int = 0

    def placeholder(self) -> int:
        """ドライランで、書き込まない代わりに使う仮の識別子（負の値）。"""
        self._next_placeholder -= 1
        return self._next_placeholder

    def say(self, message: str) -> None:
        print(message, file=self.out, flush=True)


# ---- 読み取り・書き込みの部品 -----------------------------------------------


def _query(conn: PgConnection, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]


def _query_one(conn: PgConnection, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
    rows = _query(conn, sql, params)
    return rows[0] if rows else None


def _end_source_transaction(ctx: Context) -> None:
    """移行元の読み取りトランザクションを終える（読み取りのみ。何も変更していない）。"""
    ctx.src.rollback()


def _commit(ctx: Context) -> None:
    if not ctx.options.dry_run:
        ctx.dst.commit()


def _rollback(ctx: Context) -> None:
    ctx.dst.rollback()


def _pick_unclaimed(rows: list[dict[str, Any]], claimed: set[int]) -> int | None:
    for row in rows:
        if row["id"] not in claimed:
            return int(row["id"])
    return None


# ---- ユーザ ---------------------------------------------------------------


def resolve_users(ctx: Context) -> dict[int, tuple[str, int]]:
    """移行元のアカウント → (ユーザ名, 移行先の user_id)。対応付けできないアカウントは対象外として記録する。"""
    accounts = _query(ctx.src, "SELECT id, username FROM public.accounts ORDER BY id")
    _end_source_transaction(ctx)
    wanted = set(ctx.options.usernames) if ctx.options.usernames else None
    if wanted is not None:
        for name in sorted(wanted - {a["username"] for a in accounts}):
            ctx.say(f"警告: 指定したユーザ名が移行元にありません: {name}")

    matched: dict[int, tuple[str, int]] = {}
    unmatched: dict[int, str] = {}
    for account in accounts:
        name = str(account["username"])
        if wanted is not None and name not in wanted:
            continue
        user = _query_one(ctx.dst, "SELECT id FROM public.users WHERE username = %s AND is_deleted = false", (name,))
        if user is None:
            unmatched[int(account["id"])] = name
        else:
            matched[int(account["id"])] = (name, int(user["id"]))

    # 対応付けできないアカウントのデータ件数を数えて、対象外として一覧に出す
    account_ids = {int(a["id"]) for a in accounts}
    per_account: dict[int, list[str]] = defaultdict(list)
    for table, label in (("video", "動画"), ("series", "作品"), ("playlist", "プレイリスト")):
        for row in _query(ctx.src, f"SELECT aid, count(*) AS n FROM {SRC}.{table} GROUP BY aid"):
            aid = int(row["aid"])
            if aid in matched:
                continue
            if aid in unmatched or (aid not in account_ids and wanted is None):
                per_account[aid].append(f"{label} {row['n']} 件")
    _end_source_transaction(ctx)
    for aid, parts in sorted(per_account.items()):
        label = unmatched.get(aid, f"(移行元アカウントID={aid}。アカウントなし)")
        ctx.report.add("user", "excluded", f"{label}: " + "、".join(parts))
    return matched


# ---- ジャンル・作品 -------------------------------------------------------


def migrate_system_genres(ctx: Context) -> None:
    for row in _query(ctx.src, f"SELECT * FROM {SRC}.genre WHERE aid IS NULL ORDER BY genre_id"):
        existing = _query_one(
            ctx.dst, f"SELECT id FROM {DST}.genres WHERE user_id IS NULL AND name = %s", (row["name"],)
        )
        if existing is not None:
            ctx.genre_map[int(row["genre_id"])] = int(existing["id"])
            ctx.report.add("genre", "skipped", f"共通ジャンル {row['name']}（移行先に同名あり）")
            continue
        ctx.genre_map[int(row["genre_id"])] = _insert_genre(ctx, None, row)
        ctx.report.add("genre", "migrated")
    _end_source_transaction(ctx)


def _insert_genre(ctx: Context, user_id: int | None, row: dict[str, Any]) -> int:
    if ctx.options.dry_run:
        return ctx.placeholder()
    with ctx.dst.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO {DST}.genres (user_id, name, sort_order, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
            """,
            (user_id, row["name"], row["sort_order"], row["created_at"], row["updated_at"]),
        )
        new_id = int(cur.fetchone()["id"])
    _commit(ctx)
    return new_id


def migrate_user_genres(ctx: Context, aid: int, user_id: int, username: str) -> None:
    for row in _query(ctx.src, f"SELECT * FROM {SRC}.genre WHERE aid = %s ORDER BY genre_id", (aid,)):
        try:
            existing = _query_one(
                ctx.dst, f"SELECT id FROM {DST}.genres WHERE user_id = %s AND name = %s", (user_id, row["name"])
            )
            if existing is not None:
                ctx.genre_map[int(row["genre_id"])] = int(existing["id"])
                ctx.report.add("genre", "skipped", f"{username} の独自ジャンル {row['name']}（移行先に同名あり）")
                continue
            ctx.genre_map[int(row["genre_id"])] = _insert_genre(ctx, user_id, row)
            ctx.report.add("genre", "migrated")
        except psycopg2.Error as exc:
            _rollback(ctx)
            ctx.report.add("genre", "failed", f"{username} の独自ジャンル {row['name']}: {_reason(exc)}")
    _end_source_transaction(ctx)


def migrate_series(ctx: Context, aid: int, user_id: int, username: str) -> None:
    claimed: set[int] = set()
    for row in _query(ctx.src, f"SELECT * FROM {SRC}.series WHERE aid = %s ORDER BY series_id", (aid,)):
        try:
            candidates = _query(
                ctx.dst,
                f"SELECT id FROM {DST}.series WHERE user_id = %s AND title = %s ORDER BY id",
                (user_id, row["title"]),
            )
            existing = _pick_unclaimed(candidates, claimed)
            if existing is not None:
                claimed.add(existing)
                ctx.series_map[int(row["series_id"])] = existing
                ctx.report.add("series", "skipped", f"{username} の作品 {row['title']}（移行先にあり）")
                continue
            if ctx.options.dry_run:
                new_id = ctx.placeholder()
            else:
                with ctx.dst.cursor() as cur:
                    cur.execute(
                        f"""
                        INSERT INTO {DST}.series (user_id, title, description, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s) RETURNING id
                        """,
                        (user_id, row["title"], row["description"], row["created_at"], row["updated_at"]),
                    )
                    new_id = int(cur.fetchone()["id"])
                _commit(ctx)
            claimed.add(new_id)
            ctx.series_map[int(row["series_id"])] = new_id
            ctx.report.add("series", "migrated")
        except psycopg2.Error as exc:
            _rollback(ctx)
            ctx.report.add("series", "failed", f"{username} の作品 {row['title']}: {_reason(exc)}")
    _end_source_transaction(ctx)


def _reason(exc: BaseException) -> str:
    text = str(exc).strip().splitlines()
    return f"{type(exc).__name__}: {text[0] if text else ''}"


# ---- 動画 -----------------------------------------------------------------


def _source_chunk_stats(ctx: Context, video_id: int) -> tuple[int, int]:
    row = _query_one(
        ctx.src,
        f"SELECT count(*) AS n, COALESCE(sum(byte_length), 0)::bigint AS total FROM {SRC}.video_chunk WHERE video_id = %s",
        (video_id,),
    )
    assert row is not None
    return int(row["n"]), int(row["total"])


def _copy_video(ctx: Context, video: dict[str, Any], user_id: int, expected: tuple[int, int]) -> int:
    """動画 1 件を、移行先へ 1 つのトランザクションで移行する。失敗したときは呼び出し側がロールバックする。"""
    src_id = int(video["video_id"])
    series_id = ctx.series_map.get(video["series_id"]) if video["series_id"] is not None else None
    with ctx.dst.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO {DST}.videos
                (user_id, series_id, title, description, episode_number, episode_title,
                 sort_order, duration_ms, mime_type, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'uploading', %s, %s)
            RETURNING id
            """,
            (
                user_id, series_id, video["title"], video["description"], video["episode_number"],
                video["episode_title"], video["sort_order"], video["duration_ms"], video["mime_type"],
                video["created_at"], video["updated_at"],
            ),
        )
        new_id = int(cur.fetchone()["id"])

        # チャンクは、移行元のサーバ側カーソルから 1 件ずつ読み、1 件ずつ書く（動画全体をメモリへ載せない）
        with ctx.src.cursor(name=f"mm_chunks_{src_id}", cursor_factory=RealDictCursor) as reader:
            reader.itersize = 1
            reader.execute(
                f"""
                SELECT chunk_index, start_time_ms, end_time_ms, byte_length, data
                FROM {SRC}.video_chunk WHERE video_id = %s ORDER BY chunk_index
                """,
                (src_id,),
            )
            for chunk in reader:
                cur.execute(
                    f"""
                    INSERT INTO {DST}.video_chunks
                        (video_id, chunk_index, start_time_ms, end_time_ms, byte_length, data)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        new_id, chunk["chunk_index"], chunk["start_time_ms"], chunk["end_time_ms"],
                        chunk["byte_length"], bytes(chunk["data"]),
                    ),
                )
                del chunk

        cur.execute(
            f"SELECT count(*) AS n, COALESCE(sum(byte_length), 0)::bigint AS total FROM {DST}.video_chunks WHERE video_id = %s",
            (new_id,),
        )
        got = cur.fetchone()
        if (int(got["n"]), int(got["total"])) != expected:
            raise MigrationError(
                f"チャンクの照合が一致しません 移行元(件数,バイト)={expected} 移行先=({got['n']},{got['total']})"
            )
        cur.execute(
            f"UPDATE {DST}.videos SET status = 'ready', chunk_count = %s, file_size_bytes = %s WHERE id = %s",
            (expected[0], expected[1], new_id),
        )

        thumb = None
        with ctx.src.cursor() as reader2:
            reader2.execute(f"SELECT * FROM {SRC}.thumbnail WHERE video_id = %s", (src_id,))
            thumb = reader2.fetchone()
        if thumb is not None and thumb["data"]:
            cur.execute(
                f"""
                INSERT INTO {DST}.thumbnails (video_id, mime_type, width, height, data, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (new_id, thumb["mime_type"], thumb["width"], thumb["height"], bytes(thumb["data"]), thumb["created_at"]),
            )
            ctx.report.add("thumbnail", "migrated")

        with ctx.src.cursor() as reader3:
            reader3.execute(f"SELECT genre_id, created_at FROM {SRC}.video_genre WHERE video_id = %s", (src_id,))
            links = reader3.fetchall()
        for link in links:
            genre_id = ctx.genre_map.get(int(link["genre_id"]))
            if genre_id is None:
                ctx.report.add("video_genre", "excluded", f"動画 {video['title']}: 移行されなかったジャンル(ID={link['genre_id']})")
                continue
            cur.execute(
                f"INSERT INTO {DST}.video_genres (video_id, genre_id, created_at) VALUES (%s, %s, %s)",
                (new_id, genre_id, link["created_at"]),
            )
            ctx.report.add("video_genre", "migrated")
    return new_id


def migrate_videos(ctx: Context, aid: int, user_id: int, username: str) -> None:
    rows = _query(ctx.src, f"SELECT * FROM {SRC}.video WHERE aid = %s ORDER BY video_id", (aid,))
    _end_source_transaction(ctx)
    claimed: set[int] = set()
    total = len(rows)
    for number, video in enumerate(rows, start=1):
        src_id = int(video["video_id"])
        label = f"{username} の動画「{video['title']}」(移行元ID={src_id})"
        ctx.say(f"[{number}/{total}] {username}: {video['title']}")
        if video["status"] != "ready":
            ctx.report.add("video", "excluded", f"{label} 状態={video['status']}")
            continue
        try:
            expected = _source_chunk_stats(ctx, src_id)
            _end_source_transaction(ctx)
            if expected[0] == 0:
                raise MigrationError("移行元にチャンクがありません")
            candidates = _query(
                ctx.dst,
                f"""
                SELECT id FROM {DST}.videos
                WHERE user_id = %s AND title = %s AND file_size_bytes = %s AND duration_ms = %s AND status = 'ready'
                ORDER BY id
                """,
                (user_id, video["title"], expected[1], video["duration_ms"]),
            )
            existing = _pick_unclaimed(candidates, claimed)
            if existing is not None:
                claimed.add(existing)
                ctx.video_map[src_id] = existing
                ctx.report.add("video", "skipped", f"{label} 移行済み")
                continue
            if ctx.options.dry_run:
                new_id = ctx.placeholder()
            else:
                new_id = _copy_video(ctx, video, user_id, expected)
                ctx.dst.commit()
                _end_source_transaction(ctx)
            claimed.add(new_id)
            ctx.video_map[src_id] = new_id
            ctx.report.add("video", "migrated")
            write("INF", f"動画移行成功 user={username} 移行元ID={src_id} 移行先ID={new_id} bytes={expected[1]}")
        except (psycopg2.Error, MigrationError) as exc:
            _rollback(ctx)
            _end_source_transaction(ctx)
            ctx.report.add("video", "failed", f"{label}: {_reason(exc)}")
            write("ERR", f"動画移行失敗 user={username} 移行元ID={src_id} 理由={_reason(exc)}")


# ---- 再生状態・プレイリスト・続きから視聴 -----------------------------------


def migrate_playback_states(ctx: Context, aid: int, user_id: int, username: str) -> None:
    rows = _query(ctx.src, f"SELECT * FROM {SRC}.playback_state WHERE aid = %s ORDER BY playback_id", (aid,))
    _end_source_transaction(ctx)
    for row in rows:
        new_video = ctx.video_map.get(int(row["video_id"]))
        label = f"{username} の再生状態(移行元の動画ID={row['video_id']})"
        if new_video is None:
            ctx.report.add("playback_state", "excluded", f"{label} 動画が移行されていません")
            continue
        try:
            if new_video > 0 and _query_one(
                ctx.dst,
                f"SELECT 1 FROM {DST}.playback_states WHERE user_id = %s AND video_id = %s",
                (user_id, new_video),
            ):
                ctx.report.add("playback_state", "skipped", f"{label} 移行先にあり（上書きしません）")
                continue
            if not ctx.options.dry_run:
                with ctx.dst.cursor() as cur:
                    cur.execute(
                        f"""
                        INSERT INTO {DST}.playback_states
                            (user_id, video_id, position_ms, completed, play_count, last_played_at, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            user_id, new_video, row["position_ms"], row["completed"], row["play_count"],
                            row["last_played_at"], row["created_at"], row["updated_at"],
                        ),
                    )
                _commit(ctx)
            ctx.report.add("playback_state", "migrated")
        except psycopg2.Error as exc:
            _rollback(ctx)
            ctx.report.add("playback_state", "failed", f"{label}: {_reason(exc)}")


def migrate_playlists(ctx: Context, aid: int, user_id: int, username: str) -> None:
    claimed: set[int] = set()
    for row in _query(ctx.src, f"SELECT * FROM {SRC}.playlist WHERE aid = %s ORDER BY playlist_id", (aid,)):
        src_id = int(row["playlist_id"])
        label = f"{username} のプレイリスト「{row['name']}」"
        try:
            items = _query(
                ctx.src,
                f"SELECT * FROM {SRC}.playlist_item WHERE playlist_id = %s ORDER BY sort_order, playlist_item_id",
                (src_id,),
            )
            candidates = _query(
                ctx.dst,
                f"SELECT id FROM {DST}.playlists WHERE user_id = %s AND name = %s ORDER BY id",
                (user_id, row["name"]),
            )
            existing = _pick_unclaimed(candidates, claimed)
            if existing is not None:
                claimed.add(existing)
                ctx.playlist_map[src_id] = existing
                ctx.report.add("playlist", "skipped", f"{label} 移行先にあり")
                continue

            kept: list[tuple[dict[str, Any], int]] = []
            for item in items:
                new_video = ctx.video_map.get(int(item["video_id"]))
                if new_video is None:
                    ctx.report.add("playlist_item", "excluded", f"{label} の項目(移行元の動画ID={item['video_id']}) 動画が移行されていません")
                else:
                    kept.append((item, new_video))

            if ctx.options.dry_run:
                new_playlist = ctx.placeholder()
            else:
                with ctx.dst.cursor() as cur:
                    cur.execute(
                        f"""
                        INSERT INTO {DST}.playlists (user_id, name, description, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s) RETURNING id
                        """,
                        (user_id, row["name"], row["description"], row["created_at"], row["updated_at"]),
                    )
                    new_playlist = int(cur.fetchone()["id"])
                    for order, (item, new_video) in enumerate(kept):
                        cur.execute(
                            f"""
                            INSERT INTO {DST}.playlist_items (playlist_id, video_id, sort_order, created_at)
                            VALUES (%s, %s, %s, %s) RETURNING id
                            """,
                            (new_playlist, new_video, order, item["created_at"]),
                        )
                        ctx.item_map[int(item["playlist_item_id"])] = int(cur.fetchone()["id"])
                _commit(ctx)
            claimed.add(new_playlist)
            ctx.playlist_map[src_id] = new_playlist
            ctx.report.add("playlist", "migrated")
            for _ in kept:
                ctx.report.add("playlist_item", "migrated")
        except psycopg2.Error as exc:
            _rollback(ctx)
            ctx.report.add("playlist", "failed", f"{label}: {_reason(exc)}")
    _end_source_transaction(ctx)


def migrate_playback_context(ctx: Context, aid: int, user_id: int, username: str) -> None:
    row = _query_one(ctx.src, f"SELECT * FROM {SRC}.playback_context WHERE aid = %s", (aid,))
    _end_source_transaction(ctx)
    if row is None:
        return
    label = f"{username} の続きから視聴"
    try:
        if _query_one(ctx.dst, f"SELECT 1 FROM {DST}.playback_contexts WHERE user_id = %s", (user_id,)):
            ctx.report.add("playback_context", "skipped", f"{label} 移行先にあり（上書きしません）")
            return
        # 指す先が移行されていない部分は空にする（動画側とプレイリスト側は別々に判断する）
        last_video = ctx.video_map.get(row["last_video_id"])
        playlist = ctx.playlist_map.get(row["last_playlist_id"])
        item = ctx.item_map.get(row["last_playlist_item_id"])
        video_part = last_video is not None
        # ドライランでは項目の対応を作らないため、プレイリストが対応付けできていれば移行予定とみなす
        list_part = playlist is not None and (item is not None or ctx.options.dry_run)
        if not video_part and not list_part:
            ctx.report.add("playback_context", "excluded", f"{label} 指す先の動画・プレイリストが移行されていません")
            return
        if not list_part:
            playlist = item = None
        # ドライランの仮の識別子（負の値）は書き込まない（ドライランでは書き込まない）
        if not ctx.options.dry_run:
            with ctx.dst.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {DST}.playback_contexts
                        (user_id, last_video_id, last_video_position_ms, last_video_updated_at,
                         last_playlist_id, last_playlist_item_id, last_playlist_position_ms,
                         last_playlist_updated_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id,
                        last_video,
                        row["last_video_position_ms"] if video_part else 0,
                        row["last_video_updated_at"] if video_part else None,
                        playlist,
                        item,
                        row["last_playlist_position_ms"] if list_part else 0,
                        row["last_playlist_updated_at"] if list_part else None,
                        row["updated_at"],
                    ),
                )
            _commit(ctx)
        ctx.report.add("playback_context", "migrated")
    except psycopg2.Error as exc:
        _rollback(ctx)
        ctx.report.add("playback_context", "failed", f"{label}: {_reason(exc)}")


# ---- 実行 -----------------------------------------------------------------


def run(src: PgConnection, dst: PgConnection, options: Options, out: TextIO | None = None) -> Report:
    """移行の本体。接続は呼び出し側が用意する（テストでも同じ関数を使う）。進捗は out（既定は標準エラー出力）へ出す。"""
    report = Report(dry_run=options.dry_run)
    ctx = Context(src=src, dst=dst, options=options, report=report, out=out if out is not None else sys.stderr)

    matched = resolve_users(ctx)
    ctx.say(f"移行対象のユーザ: {len(matched)} 人" + ("（ドライラン）" if options.dry_run else ""))
    migrate_system_genres(ctx)
    for aid, (username, user_id) in matched.items():
        ctx.say(f"--- {username} ---")
        migrate_user_genres(ctx, aid, user_id, username)
        migrate_series(ctx, aid, user_id, username)
        migrate_videos(ctx, aid, user_id, username)
        migrate_playback_states(ctx, aid, user_id, username)
        migrate_playlists(ctx, aid, user_id, username)
        migrate_playback_context(ctx, aid, user_id, username)
    return report


def _parse_args(argv: Sequence[str] | None) -> tuple[argparse.Namespace, Options]:
    parser = argparse.ArgumentParser(description="動画視聴サービスの DB から、本機能の DB へデータを移行する")
    parser.add_argument("--host", default=os.environ.get("MOVIE_DB_HOST", "localhost"), help="移行元のホスト")
    parser.add_argument("--port", type=int, default=int(os.environ.get("MOVIE_DB_PORT", "5432")), help="移行元のポート")
    parser.add_argument("--dbname", default=os.environ.get("MOVIE_DB_NAME", ""), help="移行元のデータベース名")
    parser.add_argument("--user", default=os.environ.get("MOVIE_DB_USER", ""), help="移行元のユーザ")
    parser.add_argument("--password", default=os.environ.get("MOVIE_DB_PASSWORD", ""), help="移行元のパスワード")
    parser.add_argument("--dry-run", action="store_true", help="書き込まず、対象と件数だけを表示する")
    parser.add_argument("--username", action="append", help="移行するユーザ名（複数指定可。省略時は対応付けできた全ユーザ）")
    args = parser.parse_args(argv)
    return args, Options(dry_run=args.dry_run, usernames=args.username)


def open_source(args: argparse.Namespace) -> PgConnection:
    conn = psycopg2.connect(
        host=args.host, port=args.port, dbname=args.dbname, user=args.user, password=args.password,
        cursor_factory=RealDictCursor,
    )
    conn.set_session(readonly=True)  # 移行元へは読み取りしか行わない
    return conn


def main(argv: Sequence[str] | None = None, *, connect_source: Callable[[argparse.Namespace], PgConnection] = open_source) -> int:
    args, options = _parse_args(argv)
    setup_logging()
    try:
        src = connect_source(args)
    except psycopg2.Error as exc:
        print(f"移行元DBへ接続できません（{args.host}:{args.port}/{args.dbname}）: {_reason(exc)}", file=sys.stderr)
        write("ERR", f"移行元DBへ接続できません host={args.host} port={args.port} dbname={args.dbname}")
        return 2
    try:
        dst = connect_target()
    except psycopg2.Error as exc:
        src.close()
        print(f"移行先DBへ接続できません（backend/.env の設定）: {_reason(exc)}", file=sys.stderr)
        write("ERR", "移行先DBへ接続できません")
        return 2
    write("INF", f"移行開始 dry_run={options.dry_run} usernames={list(options.usernames or [])}")
    try:
        report = run(src, dst, options)
    finally:
        src.close()
        dst.close()
    report.print(sys.stderr)
    write(
        "INF" if not report.failures else "WRN",
        f"移行終了 動画 移行={report.count('video', 'migrated')} スキップ={report.count('video', 'skipped')}"
        f" 対象外={report.count('video', 'excluded')} 失敗={report.count('video', 'failed')}",
    )
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
