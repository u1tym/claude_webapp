"""別サーバで稼働していたノート管理サービス（sample/note）の DB から、本機能の DB へデータを移行する。

移行元 DB と移行先 DB の両方へ同時に接続し、移行元から読んだデータを直接移行先へ書き込む。
ファイルへのエクスポート・インポートはしない。移行元へは読み取りしか行わない。

移行元のアカウント（public.accounts）のうち、--username で指定したものを、移行先の同じユーザ名の利用者のデータとして移行する。
表のパーツ（と、その表・セル・列幅）は移行しない。

使い方（backend で venv を有効化してから）:
    python scripts/migrate_from_note.py --username <ユーザ名> \\
        --host <移行元ホスト> --dbname <移行元DB名> --user <移行元ユーザ> --password <移行元パスワード> [--dry-run]

移行先の接続情報は backend/.env（または環境変数 NOTE_MANAGEMENT_ENV_FILE で指定した設定ファイル）を使う。
移行元の接続情報は環境変数でも指定できる（引数が優先）:
    NOTE_DB_HOST, NOTE_DB_PORT, NOTE_DB_NAME, NOTE_DB_USER, NOTE_DB_PASSWORD

詳細は scripts/README.md。
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
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

SRC = "note"  # 移行元のスキーマ名
DST = "note_management"  # 移行先のスキーマ名

KINDS = (
    ("folder", "フォルダ"),
    ("file", "ファイル"),
    ("part", "パーツ"),
    ("revision", "過去世代"),
    ("checklist", "チェックリスト"),
    ("category", "チェックリストのカテゴリ"),
    ("item", "チェック項目"),
)
STATUSES = (("migrated", "移行"), ("skipped", "スキップ"), ("excluded", "対象外"), ("failed", "失敗"))

# 移行先で扱う種別（移行元の「表」は含めない）
PART_TYPES = ("text", "md", "tex", "url", "action", "checklist", "jpeg", "png", "binary")
BINARY_TYPES = ("jpeg", "png", "binary")


class MigrationError(Exception):
    """1 件の移行に失敗した理由（内部理由。結果の一覧とログに出す）。"""


class MigrationAbort(Exception):
    """何も移行せずに終了する理由（利用者が無いなど）。"""


# ---- 結果の記録 -----------------------------------------------------------


@dataclass
class Report:
    dry_run: bool = False
    counts: dict[str, Counter[str]] = field(default_factory=lambda: defaultdict(Counter))
    details: dict[tuple[str, str], list[str]] = field(default_factory=lambda: defaultdict(list))

    def add(self, kind: str, status: str, detail: str | None = None, n: int = 1) -> None:
        self.counts[kind][status] += n
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
    username: str
    dry_run: bool = False


@dataclass
class Context:
    """1 回の実行の状態。移行元の識別子から、移行先の識別子への対応を持つ。"""

    src: PgConnection
    dst: PgConnection
    options: Options
    report: Report
    out: TextIO
    src_aid: int = 0
    user_id: int = 0
    folder_map: dict[int, int] = field(default_factory=dict)
    folder_path: dict[int, str] = field(default_factory=dict)
    _next_placeholder: int = 0

    def placeholder(self) -> int:
        """ドライランで、書き込まない代わりに使う仮の識別子（負の値）。"""
        self._next_placeholder -= 1
        return self._next_placeholder

    def say(self, message: str) -> None:
        print(message, file=self.out, flush=True)


# ---- 部品 -----------------------------------------------------------------


def _query(conn: PgConnection, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]


def _query_one(conn: PgConnection, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
    rows = _query(conn, sql, params)
    return rows[0] if rows else None


def _reason(exc: BaseException) -> str:
    text = str(exc).strip().splitlines()
    return f"{type(exc).__name__}: {text[0] if text else ''}"


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _decoded_size(data: str) -> int:
    try:
        return len(base64.b64decode(data, validate=True))
    except (binascii.Error, ValueError) as exc:
        raise MigrationError("画像・バイナリの中身が Base64 として読めません") from exc


def _markers(raw: Any) -> list[Any]:
    """移行元のマーカー（JSON の文字列）を、配列にする。読めないときは空。"""
    if not raw or str(raw).strip() in ("", "[]"):
        return []
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return value if isinstance(value, list) else []


# ---- 利用者 ---------------------------------------------------------------


def resolve_user(ctx: Context) -> None:
    username = ctx.options.username
    try:
        account = _query_one(ctx.src, "SELECT id FROM public.accounts WHERE username = %s", (username,))
    except psycopg2.Error as exc:
        ctx.src.rollback()
        raise MigrationAbort(f"移行元のアカウント（public.accounts）を読めません: {_reason(exc)}") from exc
    ctx.src.rollback()
    if account is None:
        raise MigrationAbort(f"移行元に、アカウント {username} がありません。何も移行せずに終了します。")
    user = _query_one(ctx.dst, "SELECT id FROM public.users WHERE username = %s AND is_deleted = false", (username,))
    if user is None:
        raise MigrationAbort(f"移行先に、利用者 {username} が無い、または論理削除済みです。何も移行せずに終了します。")
    ctx.src_aid = int(account["id"])
    ctx.user_id = int(user["id"])


# ---- フォルダ・ファイルの、移行済みの判定と並び順 ---------------------------------


def _find_existing(
    ctx: Context, table: str, key_column: str, parent_column: str, parent: int | None, name: str, deleted: bool
) -> list[dict[str, Any]]:
    """移行先の、同じ親・同じ名前・同じ削除状態の行（並び順の昇順）。"""
    if parent is not None and parent < 0:
        return []  # ドライランの仮の識別子は、移行先に存在しない
    return _query(
        ctx.dst,
        f"SELECT id FROM {DST}.{table} WHERE user_id = %s AND {parent_column} IS NOT DISTINCT FROM %s"
        f" AND {key_column} = %s AND is_deleted = %s ORDER BY sort_order, id",
        (ctx.user_id, parent, name, deleted),
    )


def _free_sort_order(ctx: Context, table: str, parent_column: str, parent: int | None, wanted: int) -> int:
    """移行元の並び順をそのまま使う。移行先の同じ親で、既に使われているときは、末尾に付ける。"""
    if parent is not None and parent < 0:
        return wanted
    used = _query_one(
        ctx.dst,
        f"SELECT 1 AS used FROM {DST}.{table} WHERE user_id = %s AND {parent_column} IS NOT DISTINCT FROM %s AND sort_order = %s",
        (ctx.user_id, parent, wanted),
    )
    if used is None:
        return wanted
    last = _query_one(
        ctx.dst,
        f"SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM {DST}.{table} WHERE user_id = %s AND {parent_column} IS NOT DISTINCT FROM %s",
        (ctx.user_id, parent),
    )
    return int(last["n"]) if last else wanted


# ---- フォルダ -------------------------------------------------------------


def _folder_order(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """親が先になる順（浅い階層から、同じ階層では、親の順・並び順）。"""
    by_parent: dict[int | None, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_parent[row["parent"]].append(row)
    for children in by_parent.values():
        children.sort(key=lambda r: (r["dorder"], r["id"]))
    ordered: list[dict[str, Any]] = []
    level = by_parent.get(None, [])
    seen: set[int] = set()
    while level:
        ordered.extend(level)
        seen.update(r["id"] for r in level)
        level = [child for row in level for child in by_parent.get(row["id"], []) if child["id"] not in seen]
    return ordered


def migrate_folders(ctx: Context) -> None:
    rows = _query(
        ctx.src,
        f"SELECT id, parent, name, dorder, deleted_number FROM {SRC}.folder WHERE aid = %s",
        (ctx.src_aid,),
    )
    ctx.src.rollback()
    by_id = {r["id"]: r for r in rows}

    def path_of(folder_id: int) -> str:
        names: list[str] = []
        cursor: int | None = folder_id
        while cursor is not None and cursor in by_id and len(names) < 100:
            names.append(str(by_id[cursor]["name"]))
            cursor = by_id[cursor]["parent"]
        return "/".join(reversed(names))

    for row in rows:
        ctx.folder_path[row["id"]] = path_of(row["id"])

    ordinals: Counter[tuple[int | None, str, bool]] = Counter()
    failed_folders: set[int] = set()
    for row in _folder_order(rows):
        label = f"フォルダ「{ctx.folder_path[row['id']]}」(移行元ID={row['id']})"
        deleted = row["deleted_number"] > 0
        if row["parent"] is not None and row["parent"] not in ctx.folder_map:
            reason = "親のフォルダが移行されていません" if row["parent"] in failed_folders or row["parent"] in by_id else "移行元に親のフォルダがありません"
            ctx.report.add("folder", "failed", f"{label}: {reason}")
            failed_folders.add(row["id"])
            continue
        parent = ctx.folder_map[row["parent"]] if row["parent"] is not None else None
        name = str(row["name"])
        # 同じ親・同じ名前・同じ削除状態の行が複数あるときは、並び順の昇順で何番目かで、移行済みかを判定する
        key = (parent, name, deleted)
        ordinal = ordinals[key]
        ordinals[key] += 1
        try:
            existing = _find_existing(ctx, "folders", "name", "parent_id", parent, name, deleted)
            if len(existing) > ordinal:
                ctx.folder_map[row["id"]] = int(existing[ordinal]["id"])
                ctx.report.add("folder", "skipped", f"{label} 移行済み")
                continue
            if ctx.options.dry_run:
                ctx.folder_map[row["id"]] = ctx.placeholder()
                ctx.report.add("folder", "migrated")
                continue
            order = _free_sort_order(ctx, "folders", "parent_id", parent, int(row["dorder"]))
            with ctx.dst.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {DST}.folders (user_id, parent_id, name, sort_order, is_deleted)"
                    " VALUES (%s, %s, %s, %s, %s) RETURNING id",
                    (ctx.user_id, parent, name, order, deleted),
                )
                ctx.folder_map[row["id"]] = int(cur.fetchone()["id"])
            ctx.dst.commit()
            ctx.report.add("folder", "migrated")
        except psycopg2.Error as exc:
            ctx.dst.rollback()
            failed_folders.add(row["id"])
            ctx.report.add("folder", "failed", f"{label}: {_reason(exc)}")
            write("ERR", f"フォルダ移行失敗 user={ctx.options.username} 移行元ID={row['id']} 理由={_reason(exc)}")


# ---- ファイル -------------------------------------------------------------


@dataclass
class SourceFile:
    row: dict[str, Any]
    parts: list[dict[str, Any]]  # 表を除く
    tables: list[dict[str, Any]]  # 表のパーツ（対象外）
    revisions: dict[int, list[dict[str, Any]]]  # 移行元のパーツ id → 過去世代
    checklists: dict[int, dict[str, Any]]  # 移行元のパーツ id → {title, categories, items, dropped_categories, dropped_items}


def _load_source_file(ctx: Context, row: dict[str, Any]) -> SourceFile:
    all_parts = _query(
        ctx.src,
        f"SELECT id, dorder, is_deleted, ptype, data, filename, title, markers, image_scale FROM {SRC}.parts"
        " WHERE aid = %s AND file = %s ORDER BY dorder, id",
        (ctx.src_aid, row["id"]),
    )
    parts = [p for p in all_parts if p["ptype"] != "table"]
    tables = [p for p in all_parts if p["ptype"] == "table"]
    revisions: dict[int, list[dict[str, Any]]] = {}
    checklists: dict[int, dict[str, Any]] = {}
    for part in parts:
        if part["ptype"] not in PART_TYPES:
            raise MigrationError(f"想定外のパーツの種別です（パーツID={part['id']} 種別={part['ptype']}）")
        if part["ptype"] in BINARY_TYPES:
            revisions[part["id"]] = _query(
                ctx.src,
                f"SELECT revision_number, ptype, filename, data, created_at FROM {SRC}.parts_revision"
                " WHERE aid = %s AND parts_id = %s ORDER BY revision_number",
                (ctx.src_aid, part["id"]),
            )
        elif part["ptype"] == "checklist":
            try:
                checklist_id = int(part["data"])
            except (TypeError, ValueError) as exc:
                raise MigrationError(f"チェックリストの識別子が読めません（パーツID={part['id']}）") from exc
            head = _query_one(ctx.src, f"SELECT id, title FROM {SRC}.checklist WHERE id = %s AND aid = %s", (checklist_id, ctx.src_aid))
            if head is None:
                raise MigrationError(f"チェックリストが移行元にありません（パーツID={part['id']} チェックリストID={checklist_id}）")
            categories = _query(
                ctx.src,
                f"SELECT id, name, dorder, is_deleted FROM {SRC}.checklist_category WHERE checklist_id = %s ORDER BY dorder, id",
                (checklist_id,),
            )
            live_ids = {c["id"] for c in categories if not c["is_deleted"]}
            items = _query(
                ctx.src,
                f"SELECT category_id, title, is_checked, dorder, is_deleted FROM {SRC}.checklist_item"
                " WHERE checklist_id = %s ORDER BY dorder, id",
                (checklist_id,),
            )
            live_items = [i for i in items if not i["is_deleted"] and i["category_id"] in live_ids]
            checklists[part["id"]] = {
                "title": head["title"],
                "categories": [c for c in categories if not c["is_deleted"]],
                "items": live_items,
                "dropped_categories": sum(1 for c in categories if c["is_deleted"]),
                "dropped_items": len(items) - len(live_items),
            }
    ctx.src.rollback()
    return SourceFile(row=row, parts=parts, tables=tables, revisions=revisions, checklists=checklists)


def _copy_file(ctx: Context, sf: SourceFile, folder_id: int, order: int) -> dict[str, int]:
    """ファイル 1 件を、移行先へ 1 つのトランザクションで作り、照合する。書き込んだ件数を返す。"""
    row = sf.row
    expected: list[tuple[int, str, int]] = []  # (移行先のパーツ id, 中身の MD5, 大きさ)
    written = Counter()
    with ctx.dst.cursor() as cur:
        cur.execute(
            f"INSERT INTO {DST}.files (user_id, folder_id, title, sort_order, is_deleted) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (ctx.user_id, folder_id, row["title"], order, row["deleted_number"] > 0),
        )
        file_id = int(cur.fetchone()["id"])
        for part in sf.parts:
            ptype = part["ptype"]
            is_binary = ptype in BINARY_TYPES
            data = "" if ptype == "checklist" else str(part["data"])
            size = _decoded_size(data) if is_binary else 0
            cur.execute(
                f"""
                INSERT INTO {DST}.parts
                    (user_id, file_id, sort_order, is_deleted, ptype, data, byte_size, filename, title, markers, image_scale)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s) RETURNING id
                """,
                (
                    ctx.user_id, file_id, part["dorder"], bool(part["is_deleted"]), ptype, data, size,
                    part["filename"] or "", part["title"] or "", json.dumps(_markers(part["markers"]), ensure_ascii=False),
                    float(part["image_scale"]) if part["image_scale"] is not None else 1.0,
                ),
            )
            part_id = int(cur.fetchone()["id"])
            written["part"] += 1
            expected.append((part_id, _md5(data), size))
            for revision in sf.revisions.get(part["id"], []):
                if revision["ptype"] not in BINARY_TYPES:
                    raise MigrationError(f"過去世代の種別が想定外です（パーツID={part['id']} 種別={revision['ptype']}）")
                cur.execute(
                    f"""
                    INSERT INTO {DST}.part_revisions
                        (user_id, part_id, revision_number, ptype, filename, data, byte_size, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        ctx.user_id, part_id, revision["revision_number"], revision["ptype"], revision["filename"],
                        revision["data"], _decoded_size(str(revision["data"])), revision["created_at"],
                    ),
                )
                written["revision"] += 1
            checklist = sf.checklists.get(part["id"])
            if checklist is not None:
                cur.execute(
                    f"INSERT INTO {DST}.checklists (user_id, part_id, title) VALUES (%s, %s, %s) RETURNING id",
                    (ctx.user_id, part_id, checklist["title"] or ""),
                )
                checklist_id = int(cur.fetchone()["id"])
                written["checklist"] += 1
                category_map: dict[int, int] = {}
                for category in checklist["categories"]:
                    cur.execute(
                        f"INSERT INTO {DST}.checklist_categories (checklist_id, name, sort_order) VALUES (%s, %s, %s) RETURNING id",
                        (checklist_id, category["name"] or "", category["dorder"]),
                    )
                    category_map[category["id"]] = int(cur.fetchone()["id"])
                    written["category"] += 1
                for item in checklist["items"]:
                    cur.execute(
                        f"""
                        INSERT INTO {DST}.checklist_items (checklist_id, category_id, title, is_checked, sort_order)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (checklist_id, category_map[item["category_id"]], item["title"] or "", bool(item["is_checked"]), item["dorder"]),
                    )
                    written["item"] += 1

        # 照合: 件数と、中身の大きさ・MD5
        cur.execute(
            f"SELECT id, byte_size, md5(data) AS digest FROM {DST}.parts WHERE file_id = %s", (file_id,)
        )
        actual = {int(r["id"]): (r["digest"], int(r["byte_size"])) for r in cur.fetchall()}
        if len(actual) != len(sf.parts):
            raise MigrationError(f"パーツ数の照合が一致しません 期待={len(sf.parts)} 移行先={len(actual)}")
        for part_id, digest, size in expected:
            if actual.get(part_id) != (digest, size):
                raise MigrationError(f"パーツの中身の照合が一致しません（移行先パーツID={part_id}）")
        counts = {
            "revision": (f"SELECT count(*) AS n FROM {DST}.part_revisions r JOIN {DST}.parts p ON p.id = r.part_id WHERE p.file_id = %s", written["revision"]),
            "checklist": (f"SELECT count(*) AS n FROM {DST}.checklists c JOIN {DST}.parts p ON p.id = c.part_id WHERE p.file_id = %s", written["checklist"]),
            "category": (
                f"SELECT count(*) AS n FROM {DST}.checklist_categories k JOIN {DST}.checklists c ON c.id = k.checklist_id"
                f" JOIN {DST}.parts p ON p.id = c.part_id WHERE p.file_id = %s",
                written["category"],
            ),
            "item": (
                f"SELECT count(*) AS n FROM {DST}.checklist_items i JOIN {DST}.checklists c ON c.id = i.checklist_id"
                f" JOIN {DST}.parts p ON p.id = c.part_id WHERE p.file_id = %s",
                written["item"],
            ),
        }
        for kind, (sql, want) in counts.items():
            cur.execute(sql, (file_id,))
            got = int(cur.fetchone()["n"])
            if got != want:
                raise MigrationError(f"{kind} の件数の照合が一致しません 期待={want} 移行先={got}")
    return dict(written)


def _record_file(ctx: Context, sf: SourceFile, label: str, written: dict[str, int] | None) -> None:
    """結果の集計。written が None のときは、ドライラン（移行予定として、移行元の件数を数える）。"""
    checklists = list(sf.checklists.values())
    revision_total = sum(len(v) for v in sf.revisions.values())
    if written is None:
        written = {
            "part": len(sf.parts),
            "revision": revision_total,
            "checklist": len(checklists),
            "category": sum(len(c["categories"]) for c in checklists),
            "item": sum(len(c["items"]) for c in checklists),
        }
    ctx.report.add("file", "migrated")
    for kind in ("part", "revision", "checklist", "category", "item"):
        ctx.report.add(kind, "migrated", n=written.get(kind, 0))
    for table in sf.tables:
        ctx.report.add("part", "excluded", f"{label} 並び順{table['dorder']}: 表のパーツ（移行しません）")
    for checklist in checklists:
        if checklist["dropped_categories"]:
            ctx.report.add("category", "excluded", f"{label}: 削除済みのカテゴリ {checklist['dropped_categories']} 件（元に戻す操作がないため移行しません）", n=checklist["dropped_categories"])
        if checklist["dropped_items"]:
            ctx.report.add("item", "excluded", f"{label}: 削除済みの項目 {checklist['dropped_items']} 件（元に戻す操作がないため移行しません）", n=checklist["dropped_items"])


def migrate_files(ctx: Context) -> None:
    rows = _query(
        ctx.src,
        f"SELECT id, belong, title, dorder, deleted_number FROM {SRC}.file WHERE aid = %s ORDER BY belong, dorder, id",
        (ctx.src_aid,),
    )
    ctx.src.rollback()
    total = len(rows)
    ordinals: Counter[tuple[int | None, str, bool]] = Counter()
    for number, row in enumerate(rows, start=1):
        path = ctx.folder_path.get(row["belong"], f"(フォルダID={row['belong']})")
        label = f"ファイル「{path}/{row['title']}」(移行元ID={row['id']})"
        ctx.say(f"[{number}/{total}] {path}/{row['title']}")
        if row["belong"] not in ctx.folder_map:
            ctx.report.add("file", "failed", f"{label}: 所属フォルダが移行されていません")
            continue
        folder_id = ctx.folder_map[row["belong"]]
        title = str(row["title"])
        deleted = row["deleted_number"] > 0
        key = (folder_id, title, deleted)
        ordinal = ordinals[key]
        ordinals[key] += 1
        try:
            existing = _find_existing(ctx, "files", "title", "folder_id", folder_id, title, deleted)
            if len(existing) > ordinal:
                ctx.report.add("file", "skipped", f"{label} 移行済み")
                continue
            sf = _load_source_file(ctx, row)
            if ctx.options.dry_run:
                _record_file(ctx, sf, label, None)
                continue
            order = _free_sort_order(ctx, "files", "folder_id", folder_id, int(row["dorder"]))
            written = _copy_file(ctx, sf, folder_id, order)
            ctx.dst.commit()
            _record_file(ctx, sf, label, written)
            write(
                "INF",
                f"ファイル移行成功 user={ctx.options.username} 移行元ID={row['id']} パーツ={written.get('part', 0)}"
                f" 過去世代={written.get('revision', 0)} チェックリスト={written.get('checklist', 0)}",
            )
        except (psycopg2.Error, MigrationError) as exc:
            ctx.dst.rollback()
            ctx.src.rollback()
            ctx.report.add("file", "failed", f"{label}: {_reason(exc)}")
            write("ERR", f"ファイル移行失敗 user={ctx.options.username} 移行元ID={row['id']} 理由={_reason(exc)}")


# ---- 実行 -----------------------------------------------------------------


def run(src: PgConnection, dst: PgConnection, options: Options, out: TextIO | None = None) -> Report:
    """移行の本体。接続は呼び出し側が用意する（テストでも同じ関数を使う）。進捗は out（既定は標準エラー出力）へ出す。"""
    report = Report(dry_run=options.dry_run)
    ctx = Context(src=src, dst=dst, options=options, report=report, out=out if out is not None else sys.stderr)
    resolve_user(ctx)
    ctx.say(f"移行先の利用者: {options.username}" + ("（ドライラン）" if options.dry_run else ""))
    migrate_folders(ctx)
    migrate_files(ctx)
    return report


def _parse_args(argv: Sequence[str] | None) -> tuple[argparse.Namespace, Options]:
    parser = argparse.ArgumentParser(description="ノート管理サービスの DB から、本機能の DB へデータを移行する")
    parser.add_argument("--username", required=True, help="移行元のアカウント名（移行先の同名の利用者のデータとして移行する）")
    parser.add_argument("--host", default=os.environ.get("NOTE_DB_HOST", "localhost"), help="移行元のホスト")
    parser.add_argument("--port", type=int, default=int(os.environ.get("NOTE_DB_PORT", "5432")), help="移行元のポート")
    parser.add_argument("--dbname", default=os.environ.get("NOTE_DB_NAME", ""), help="移行元のデータベース名")
    parser.add_argument("--user", default=os.environ.get("NOTE_DB_USER", ""), help="移行元のユーザ")
    parser.add_argument("--password", default=os.environ.get("NOTE_DB_PASSWORD", ""), help="移行元のパスワード")
    parser.add_argument("--dry-run", action="store_true", help="書き込まず、対象と件数だけを表示する")
    args = parser.parse_args(argv)
    return args, Options(username=args.username, dry_run=args.dry_run)


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
    write("INF", f"移行開始 dry_run={options.dry_run} username={options.username}")
    try:
        report = run(src, dst, options)
    except MigrationAbort as exc:
        print(str(exc), file=sys.stderr)
        write("ERR", f"移行を中止 理由={exc}")
        return 2
    finally:
        src.close()
        dst.close()
    report.print(sys.stderr)
    write(
        "INF" if not report.failures else "WRN",
        f"移行終了 フォルダ 移行={report.count('folder', 'migrated')} スキップ={report.count('folder', 'skipped')}"
        f" 失敗={report.count('folder', 'failed')} / ファイル 移行={report.count('file', 'migrated')}"
        f" スキップ={report.count('file', 'skipped')} 失敗={report.count('file', 'failed')}",
    )
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
