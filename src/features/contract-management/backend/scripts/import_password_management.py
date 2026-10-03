"""password-management の削除されていないパスワードエントリを、契約を伴わない契約として取り込む（REQ-010）。

- 取り込み元（`password_management.entries`）は読み取りだけで、変更しない。
- 取り込み先の接続情報は `backend/.env`（`app.db` 経由。`CONTRACT_MANAGEMENT_ENV_FILE` で切り替え可）。
  取り込み元は、取り込み先と同じ DB のスキーマ `password_management` を直接読む（1 回限りの移行の例外）。
- 写し方: 名称←タイトル、ユーザ名←ユーザ名、パスワード←パスワード、ホームページ←サイトURL、メモ←メモ。
  区分は「その他」（なければ作る）、ステータスは有効、ログイン方法はユーザ名とパスワード。
- 取り込み元の行の ID を `imported_from_entry_id` に控えるので、何度実行しても重複して取り込まない。
- 論理削除済みのエントリと、論理削除済みの利用者のエントリは、取り込まない。
- 件数と、取り込めなかったエントリの ID・理由を出力する。パスワード・ユーザ名・タイトルの値は、出力にも、ログにも出さない。

使い方（このバックエンドの venv を有効化してから）:
    python scripts/import_password_management.py --dry-run   # 書き込まずに結果だけ確認する
    python scripts/import_password_management.py             # 取り込む
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from psycopg2.extensions import connection as PgConnection  # noqa: E402

from app import repos  # noqa: E402
from app.db import connect  # noqa: E402
from app.logger import write  # noqa: E402

NAME_MAX = 200
_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


@dataclass
class ImportResult:
    target: int = 0  # 取り込み元の、削除されていない（利用者も削除されていない）エントリ数
    imported: int = 0
    already_imported: int = 0
    skipped_deleted_user: int = 0  # 論理削除済みの利用者のエントリ数（対象に含めない）
    failures: list[tuple[int, str]] = field(default_factory=list)  # (エントリ ID, 理由)


def _source_exists(conn: PgConnection, schema: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_schema = %s AND table_name = 'entries'",
            (schema,),
        )
        return cur.fetchone() is not None


def _default_category_id(conn: PgConnection, user_id: int, cache: dict[int, int]) -> int:
    if user_id not in cache:
        repos.ensure_default_category(conn, user_id)
        cache[user_id] = next(c.id for c in repos.list_categories(conn, user_id) if c.is_default)
    return cache[user_id]


def run_import(conn: PgConnection, source_schema: str = "password_management") -> ImportResult:
    """取り込む。トランザクションの確定（commit）は、呼び出し側が行う。"""
    if not _IDENTIFIER.match(source_schema):
        raise ValueError("取り込み元のスキーマ名が不正")
    if not _source_exists(conn, source_schema):
        raise RuntimeError(f"取り込み元の表 {source_schema}.entries が見つからない")

    result = ImportResult()
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT e.id, e.user_id, e.title, e.userword, e.psword, e.site, e.memo, u.is_deleted AS user_deleted
            FROM {source_schema}.entries e
            JOIN public.users u ON u.id = e.user_id
            WHERE e.is_deleted = false
            ORDER BY e.id
            """
        )
        entries = [dict(r) for r in cur.fetchall()]

    categories: dict[int, int] = {}
    for e in entries:
        entry_id = int(e["id"])
        if e["user_deleted"]:
            result.skipped_deleted_user += 1
            continue
        result.target += 1
        name = str(e["title"]).strip()
        if name == "":
            result.failures.append((entry_id, "名称（タイトル）が空"))
            continue
        if len(name) > NAME_MAX:
            result.failures.append((entry_id, f"名称（タイトル）が {NAME_MAX} 文字を超える"))
            continue
        username = str(e["userword"]).strip() or None
        site = (str(e["site"]).strip() or None) if e["site"] is not None else None
        memo = (str(e["memo"]).strip() or None) if e["memo"] is not None else None
        with conn.cursor() as cur:
            cur.execute("SAVEPOINT import_entry")
            try:
                category_id = _default_category_id(conn, int(e["user_id"]), categories)
                cur.execute(
                    """
                    INSERT INTO contract_management.contracts
                        (user_id, category_id, name, has_contract, status, homepage, memo,
                         login_password, username, password, imported_from_entry_id)
                    VALUES (%s, %s, %s, false, 'active', %s, %s, true, %s, %s, %s)
                    ON CONFLICT (imported_from_entry_id) WHERE imported_from_entry_id IS NOT NULL DO NOTHING
                    RETURNING id
                    """,
                    (e["user_id"], category_id, name, site, memo, username, e["psword"], entry_id),
                )
                inserted = cur.fetchone() is not None
            except Exception as exc:  # 1 件の失敗で、全体を止めない（理由は、種類だけを出す）
                cur.execute("ROLLBACK TO SAVEPOINT import_entry")
                result.failures.append((entry_id, f"登録に失敗 {type(exc).__name__}"))
                continue
            cur.execute("RELEASE SAVEPOINT import_entry")
        if inserted:
            result.imported += 1
        else:
            result.already_imported += 1
    return result


def _report(result: ImportResult, dry_run: bool) -> str:
    lines = [
        ("【ドライラン: 書き込みなし】" if dry_run else "【取り込み完了】"),
        f"対象のエントリ: {result.target} 件",
        f"取り込み{'（予定）' if dry_run else ''}: {result.imported} 件",
        f"取り込み済みのためスキップ: {result.already_imported} 件",
        f"取り込めなかった: {len(result.failures)} 件",
    ]
    if result.skipped_deleted_user:
        lines.append(f"論理削除済みの利用者のエントリ（対象外）: {result.skipped_deleted_user} 件")
    for entry_id, reason in result.failures:
        lines.append(f"  - 取り込み元のエントリ ID {entry_id}: {reason}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="password-management のエントリを、契約を伴わない契約として取り込む")
    parser.add_argument("--dry-run", action="store_true", help="書き込まず、結果だけを表示する")
    parser.add_argument("--source-schema", default="password_management", help="取り込み元のスキーマ名（既定: password_management）")
    args = parser.parse_args(argv)

    try:
        conn = connect()
    except Exception as exc:
        # 接続情報（パスワードを含む）は出さない。どの接続先か（取り込み先の DB）と、失敗の種類だけを示す
        print(f"取り込み先の DB に接続できません（{type(exc).__name__}）。backend/.env を確認してください。", file=sys.stderr)
        return 2
    try:
        write("INF", f"取り込み開始 dry_run={args.dry_run} source_schema={args.source_schema}")
        try:
            result = run_import(conn, args.source_schema)
        except (RuntimeError, ValueError) as exc:
            conn.rollback()
            write("ERR", f"取り込み失敗 理由={exc}")
            print(f"取り込めません: {exc}", file=sys.stderr)
            return 2
        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()
        write(
            "INF",
            f"取り込み終了 dry_run={args.dry_run} 対象={result.target} 取り込み={result.imported} "
            f"取り込み済み={result.already_imported} 失敗={len(result.failures)}",
        )
        for entry_id, reason in result.failures:
            write("WRN", f"取り込めなかった entry_id={entry_id} 理由={reason}")
        print(_report(result, args.dry_run))
        return 1 if result.failures else 0
    except Exception as exc:
        conn.rollback()
        write("ERR", f"取り込み失敗 type={type(exc).__name__}")
        print(f"取り込みに失敗しました（{type(exc).__name__}）。ログを確認してください。", file=sys.stderr)
        return 2
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
