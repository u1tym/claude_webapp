"""export_from_psinfo.py が出力した JSON を読み込み、本プロジェクトの
password_management.entries へ取り込むスクリプト。

このスクリプトは本プロジェクトの DB に到達できる環境（このバックエンドの venv）で実行する。
接続情報は `backend/.env` を使う（`app.db` 経由）。

旧システムのユーザ（アカウント名）と、本プロジェクトの `public.users.username` を突合し、
一致するユーザのぶんだけを取り込む。一致しないユーザ、および移行先で既にタイトルが
重複するエントリはスキップし、最後に一覧表示する。

パスワードの値は標準出力・ログのいずれにも出力しない。

使い方（このディレクトリの venv を有効化してから）:
    python scripts/import_to_password_management.py --input psinfo_export.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.repos import get_user_by_username, insert_entry, title_exists  # noqa: E402


def _parse_args() -> str:
    parser = argparse.ArgumentParser(description="psinfo のエクスポート JSON を取り込む")
    parser.add_argument("--input", required=True, help="export_from_psinfo.py が出力した JSON ファイルパス")
    args = parser.parse_args()
    return args.input


def main() -> None:
    input_path = _parse_args()
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    accounts: dict[int, str] = {int(a["id"]): str(a["username"]) for a in data["accounts"]}
    entries: list[dict[str, object]] = data["entries"]

    imported = 0
    skipped_duplicate: list[tuple[str, str]] = []
    unmatched: dict[str, int] = {}

    for entry in entries:
        aid = int(entry["aid"])  # type: ignore[arg-type]
        old_username = accounts.get(aid)
        if old_username is None:
            key = f"(旧アカウントID={aid}、旧アカウント情報に無い)"
            unmatched[key] = unmatched.get(key, 0) + 1
            continue

        user = get_user_by_username(old_username)
        if user is None or user.is_deleted:
            unmatched[old_username] = unmatched.get(old_username, 0) + 1
            continue

        title = str(entry["title"])
        if title_exists(user.id, title):
            skipped_duplicate.append((old_username, title))
            continue

        insert_entry(
            user.id,
            title,
            str(entry["userword"]),
            str(entry["psword"]),
            entry["site"],  # type: ignore[arg-type]
            entry["memo"],  # type: ignore[arg-type]
        )
        imported += 1

    print(f"移行成功: {imported}件", file=sys.stderr)

    if unmatched:
        print("対象外（本プロジェクトに一致するユーザが無い、または削除済み）:", file=sys.stderr)
        for name, count in sorted(unmatched.items()):
            print(f"  {name}: {count}件", file=sys.stderr)

    if skipped_duplicate:
        print("スキップ（移行先で既に同じタイトルが登録済み）:", file=sys.stderr)
        for username, title in skipped_duplicate:
            print(f"  {username}: {title}", file=sys.stderr)

    print(
        f"合計: 成功 {imported}件 / 対象外 {sum(unmatched.values())}件 / 重複スキップ {len(skipped_duplicate)}件",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
