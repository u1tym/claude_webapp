"""別サーバで稼働していたレシピ管理サービス（sample/recipe）の DB から、本機能の DB へデータを移行する。

移行元 DB と移行先 DB の両方へ同時に接続し、移行元から読んだデータを直接移行先へ書き込む。
ファイルへのエクスポート・インポートはしない。移行元へは読み取りしか行わない。

移行元は利用者を持たないため、すべてのデータを、--username で指定した 1 人の利用者のものとして移行する。

使い方（backend で venv を有効化してから）:
    python scripts/migrate_from_recipe.py --username <移行先の利用者名> \\
        --host <移行元ホスト> --dbname <移行元DB名> --user <移行元ユーザ> --password <移行元パスワード> [--dry-run]

移行先の接続情報は backend/.env（または環境変数 RECIPE_MANAGEMENT_ENV_FILE で指定した設定ファイル）を使う。
移行元の接続情報は環境変数でも指定できる（引数が優先）:
    RECIPE_DB_HOST, RECIPE_DB_PORT, RECIPE_DB_NAME, RECIPE_DB_USER, RECIPE_DB_PASSWORD

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

SRC = "recipe"  # 移行元のスキーマ名
DST = "recipe_management"  # 移行先のスキーマ名

KINDS = (
    ("recipe", "レシピ"),
    ("step", "工程"),
    ("item", "材料の行"),
    ("ingredient", "材料"),
    ("measurement", "分量名称"),
)
STATUSES = (("migrated", "移行"), ("skipped", "スキップ"), ("excluded", "対象外"), ("failed", "失敗"))


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
    user_id: int = 0
    ingredient_map: dict[int, int] = field(default_factory=dict)
    measurement_map: dict[int, int] = field(default_factory=dict)
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


# ---- 利用者 ---------------------------------------------------------------


def resolve_user(ctx: Context) -> None:
    user = _query_one(
        ctx.dst, "SELECT id FROM public.users WHERE username = %s AND is_deleted = false", (ctx.options.username,)
    )
    if user is None:
        raise MigrationAbort(
            f"移行先に、利用者 {ctx.options.username} が無い、または論理削除済みです。何も移行せずに終了します。"
        )
    ctx.user_id = int(user["id"])


# ---- 材料・分量名称 -------------------------------------------------------


def migrate_ingredients(ctx: Context) -> None:
    rows = _query(ctx.src, f"SELECT id, name, kana FROM {SRC}.ingredient ORDER BY id")
    for row in rows:
        name = str(row["name"])
        try:
            common = _query_one(ctx.dst, f"SELECT id FROM {DST}.ingredients WHERE user_id IS NULL AND name = %s", (name,))
            if common is not None:
                ctx.ingredient_map[int(row["id"])] = int(common["id"])
                ctx.report.add("ingredient", "skipped", f"{name}（共通の材料に対応付け）")
                continue
            own = _query_one(
                ctx.dst, f"SELECT id FROM {DST}.ingredients WHERE user_id = %s AND name = %s", (ctx.user_id, name)
            )
            if own is not None:
                ctx.ingredient_map[int(row["id"])] = int(own["id"])
                ctx.report.add("ingredient", "skipped", f"{name}（移行先の独自の材料に対応付け）")
                continue
            if ctx.options.dry_run:
                new_id = ctx.placeholder()
            else:
                with ctx.dst.cursor() as cur:
                    cur.execute(
                        f"INSERT INTO {DST}.ingredients (user_id, name, kana) VALUES (%s, %s, %s) RETURNING id",
                        (ctx.user_id, name, row["kana"]),
                    )
                    new_id = int(cur.fetchone()["id"])
                ctx.dst.commit()
            ctx.ingredient_map[int(row["id"])] = new_id
            ctx.report.add("ingredient", "migrated")
        except psycopg2.Error as exc:
            ctx.dst.rollback()
            ctx.report.add("ingredient", "failed", f"{name}: {_reason(exc)}")
    ctx.src.rollback()


def migrate_measurements(ctx: Context) -> None:
    rows = _query(ctx.src, f"SELECT id, name_bef, name_aft, ness_amount FROM {SRC}.measurements ORDER BY id")
    for row in rows:
        bef, aft = str(row["name_bef"]), str(row["name_aft"])
        label = f"{bef}/{aft}"
        try:
            existing = _query_one(
                ctx.dst,
                f"SELECT id, ness_amount, (user_id IS NULL) AS is_system FROM {DST}.measurements "
                "WHERE name_bef = %s AND name_aft = %s AND (user_id IS NULL OR user_id = %s) "
                "ORDER BY user_id NULLS FIRST LIMIT 1",
                (bef, aft, ctx.user_id),
            )
            if existing is not None:
                ctx.measurement_map[int(row["id"])] = int(existing["id"])
                where = "共通の分量名称" if existing["is_system"] else "移行先の独自の分量名称"
                note = ""
                if bool(existing["ness_amount"]) != bool(row["ness_amount"]):
                    note = (
                        f" ※数量の要否が違います（移行元={bool(row['ness_amount'])}"
                        f" 移行先={bool(existing['ness_amount'])}）。移行先を変更しません"
                    )
                ctx.report.add("measurement", "skipped", f"{label}（{where}に対応付け）{note}")
                continue
            if ctx.options.dry_run:
                new_id = ctx.placeholder()
            else:
                with ctx.dst.cursor() as cur:
                    cur.execute(
                        f"INSERT INTO {DST}.measurements (user_id, name_bef, name_aft, ness_amount)"
                        " VALUES (%s, %s, %s, %s) RETURNING id",
                        (ctx.user_id, bef, aft, bool(row["ness_amount"])),
                    )
                    new_id = int(cur.fetchone()["id"])
                ctx.dst.commit()
            ctx.measurement_map[int(row["id"])] = new_id
            ctx.report.add("measurement", "migrated")
        except psycopg2.Error as exc:
            ctx.dst.rollback()
            ctx.report.add("measurement", "failed", f"{label}: {_reason(exc)}")
    ctx.src.rollback()


# ---- レシピ ---------------------------------------------------------------


def _copy_recipe(ctx: Context, menu: dict[str, Any], steps: list[dict[str, Any]]) -> tuple[int, int, int]:
    """レシピ 1 件を、移行先へ 1 つのトランザクションで作る。(工程数, 材料の行数, 取り除いた行数) を返す。"""
    dropped = 0
    written_items = 0
    with ctx.dst.cursor() as cur:
        cur.execute(
            f"INSERT INTO {DST}.recipes (user_id, name, kana) VALUES (%s, %s, %s) RETURNING id",
            (ctx.user_id, menu["name"], menu["kana"]),
        )
        recipe_id = int(cur.fetchone()["id"])
        for step in steps:
            cur.execute(
                f"INSERT INTO {DST}.recipe_steps (recipe_id, step_no, description) VALUES (%s, %s, %s) RETURNING id",
                (recipe_id, step["step"], step["description"]),
            )
            step_id = int(cur.fetchone()["id"])
            item_no = 0
            for item in step["items"]:
                ingredient = ctx.ingredient_map.get(int(item["ingredient_id"]))
                measurement = ctx.measurement_map.get(int(item["measurement_id"]))
                if ingredient is None or measurement is None:
                    dropped += 1
                    ctx.report.add(
                        "item", "excluded",
                        f"レシピ「{menu['name']}」手順{step['step']}: 移行元に存在しない材料・分量名称を指す行"
                        f"（材料ID={item['ingredient_id']} 分量名称ID={item['measurement_id']}）を取り除きました",
                    )
                    continue
                item_no += 1
                cur.execute(
                    f"INSERT INTO {DST}.recipe_step_items (step_id, item_no, ingredient_id, measurement_id, amount)"
                    " VALUES (%s, %s, %s, %s, %s)",
                    (step_id, item_no, ingredient, measurement, item["amount"]),
                )
                written_items += 1
        cur.execute(f"SELECT count(*) AS n FROM {DST}.recipe_steps WHERE recipe_id = %s", (recipe_id,))
        step_count = int(cur.fetchone()["n"])
        cur.execute(
            f"SELECT count(*) AS n FROM {DST}.recipe_step_items i JOIN {DST}.recipe_steps s ON s.id = i.step_id"
            " WHERE s.recipe_id = %s",
            (recipe_id,),
        )
        item_count = int(cur.fetchone()["n"])
    if (step_count, item_count) != (len(steps), written_items):
        raise MigrationError(
            f"工程数・材料の行数の照合が一致しません 期待=({len(steps)},{written_items}) 移行先=({step_count},{item_count})"
        )
    return step_count, item_count, dropped


def migrate_recipes(ctx: Context) -> None:
    menus = _query(ctx.src, f"SELECT id, name, kana, is_deleted FROM {SRC}.menu ORDER BY id")
    total = len(menus)
    for number, menu in enumerate(menus, start=1):
        label = f"レシピ「{menu['name']}」(移行元ID={menu['id']})"
        ctx.say(f"[{number}/{total}] {menu['name']}")
        if menu["is_deleted"]:
            ctx.report.add("recipe", "excluded", f"{label} 削除済み")
            continue
        try:
            steps = _query(
                ctx.src, f"SELECT id, step, description FROM {SRC}.menu_step WHERE menu_id = %s ORDER BY step, id", (menu["id"],)
            )
            for step in steps:
                step["items"] = _query(
                    ctx.src,
                    f"SELECT ingredient_id, measurement_id, amount FROM {SRC}.menu_step_ingredient"
                    " WHERE menu_step_id = %s ORDER BY id",
                    (step["id"],),
                )
            ctx.src.rollback()
            if _query_one(
                ctx.dst,
                f"SELECT 1 FROM {DST}.recipes WHERE user_id = %s AND name = %s AND is_deleted = false",
                (ctx.user_id, menu["name"]),
            ):
                ctx.report.add("recipe", "skipped", f"{label} 移行済み")
                continue
            item_total = sum(len(step["items"]) for step in steps)
            if ctx.options.dry_run:
                ctx.report.add("recipe", "migrated")
                for _ in steps:
                    ctx.report.add("step", "migrated")
                for step in steps:
                    for item in step["items"]:
                        if int(item["ingredient_id"]) in ctx.ingredient_map and int(item["measurement_id"]) in ctx.measurement_map:
                            ctx.report.add("item", "migrated")
                        else:
                            ctx.report.add("item", "excluded", f"{label}: 移行元に存在しない材料・分量名称を指す行")
                continue
            step_count, item_count, dropped = _copy_recipe(ctx, menu, steps)
            ctx.dst.commit()
            ctx.report.add("recipe", "migrated")
            for _ in range(step_count):
                ctx.report.add("step", "migrated")
            for _ in range(item_count):
                ctx.report.add("item", "migrated")
            write("INF", f"レシピ移行成功 user={ctx.options.username} 移行元ID={menu['id']} 工程={step_count} 材料の行={item_count}/{item_total}")
        except (psycopg2.Error, MigrationError) as exc:
            ctx.dst.rollback()
            ctx.src.rollback()
            ctx.report.add("recipe", "failed", f"{label}: {_reason(exc)}")
            write("ERR", f"レシピ移行失敗 user={ctx.options.username} 移行元ID={menu['id']} 理由={_reason(exc)}")


# ---- 実行 -----------------------------------------------------------------


def run(src: PgConnection, dst: PgConnection, options: Options, out: TextIO | None = None) -> Report:
    """移行の本体。接続は呼び出し側が用意する（テストでも同じ関数を使う）。進捗は out（既定は標準エラー出力）へ出す。"""
    report = Report(dry_run=options.dry_run)
    ctx = Context(src=src, dst=dst, options=options, report=report, out=out if out is not None else sys.stderr)
    resolve_user(ctx)
    ctx.say(f"移行先の利用者: {options.username}" + ("（ドライラン）" if options.dry_run else ""))
    migrate_ingredients(ctx)
    migrate_measurements(ctx)
    migrate_recipes(ctx)
    return report


def _parse_args(argv: Sequence[str] | None) -> tuple[argparse.Namespace, Options]:
    parser = argparse.ArgumentParser(description="レシピ管理サービスの DB から、本機能の DB へデータを移行する")
    parser.add_argument("--username", required=True, help="移行先の利用者名（全データをこの利用者のものとして移行する）")
    parser.add_argument("--host", default=os.environ.get("RECIPE_DB_HOST", "localhost"), help="移行元のホスト")
    parser.add_argument("--port", type=int, default=int(os.environ.get("RECIPE_DB_PORT", "5432")), help="移行元のポート")
    parser.add_argument("--dbname", default=os.environ.get("RECIPE_DB_NAME", ""), help="移行元のデータベース名")
    parser.add_argument("--user", default=os.environ.get("RECIPE_DB_USER", ""), help="移行元のユーザ")
    parser.add_argument("--password", default=os.environ.get("RECIPE_DB_PASSWORD", ""), help="移行元のパスワード")
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
        f"移行終了 レシピ 移行={report.count('recipe', 'migrated')} スキップ={report.count('recipe', 'skipped')}"
        f" 対象外={report.count('recipe', 'excluded')} 失敗={report.count('recipe', 'failed')}",
    )
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
