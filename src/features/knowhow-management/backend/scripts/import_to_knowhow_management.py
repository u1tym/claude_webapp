"""export_from_knowhow.py が出力した JSON を読み込み、本プロジェクトの
knowhow_management スキーマへ取り込むスクリプト。

このスクリプトは本プロジェクトの DB に到達できる環境（このバックエンドの venv）で実行する。
接続情報は `backend/.env` を使う（`app.db` 経由）。

旧システムのユーザ（アカウント名）と、本プロジェクトの `public.users.username` を突合し、
一致するユーザのぶんだけを取り込む。大項目→中項目→ノウハウの順に、旧IDと新IDの対応を
保ちながら挿入する。表示順は移行元の値をそのまま使う。

使い方（このディレクトリの venv を有効化してから）:
    python scripts/import_to_knowhow_management.py --input knowhow_export.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.db import get_conn  # noqa: E402
from app.repos import (  # noqa: E402
    get_user_by_username,
    major_category_name_exists,
    middle_category_name_exists,
)


def _parse_args() -> str:
    parser = argparse.ArgumentParser(description="knowhow のエクスポート JSON を取り込む")
    parser.add_argument("--input", required=True, help="export_from_knowhow.py が出力した JSON ファイルパス")
    args = parser.parse_args()
    return args.input


def _insert_major_category(user_id: int, name: str, display_order: int) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO knowhow_management.major_categories (user_id, name, display_order)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (user_id, name, display_order),
            )
            return int(cur.fetchone()["id"])


def _insert_middle_category(user_id: int, major_category_id: int, name: str, display_order: int) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO knowhow_management.middle_categories
                    (user_id, major_category_id, name, display_order)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (user_id, major_category_id, name, display_order),
            )
            return int(cur.fetchone()["id"])


def _insert_knowhow(
    user_id: int,
    middle_category_id: int | None,
    title: str,
    keywords: str | None,
    content: str,
    display_order: int,
) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO knowhow_management.knowhows
                    (user_id, middle_category_id, title, keywords, content, display_order)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (user_id, middle_category_id, title, keywords, content, display_order),
            )
            return int(cur.fetchone()["id"])


def main() -> None:
    input_path = _parse_args()
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    accounts: dict[int, str] = {int(a["id"]): str(a["username"]) for a in data["accounts"]}
    user_cache: dict[int, int | None] = {}

    def resolve_user(aid: int) -> int | None:
        if aid in user_cache:
            return user_cache[aid]
        username = accounts.get(aid)
        if username is None:
            user_cache[aid] = None
            return None
        user = get_user_by_username(username)
        result = user.id if (user is not None and not user.is_deleted) else None
        user_cache[aid] = result
        return result

    def account_label(aid: int) -> str:
        return accounts.get(aid, f"(旧アカウントID={aid})")

    major_id_map: dict[int, int] = {}
    major_success = 0
    major_skipped_dup: list[tuple[str, str]] = []
    major_unmatched: dict[str, int] = {}

    for m in data["major_categories"]:
        aid = int(m["aid"])
        user_id = resolve_user(aid)
        if user_id is None:
            label = account_label(aid)
            major_unmatched[label] = major_unmatched.get(label, 0) + 1
            continue
        if major_category_name_exists(user_id, m["name"]):
            major_skipped_dup.append((account_label(aid), m["name"]))
            continue
        new_id = _insert_major_category(user_id, m["name"], int(m["display_order"]))
        major_id_map[int(m["id"])] = new_id
        major_success += 1

    middle_id_map: dict[int, int] = {}
    middle_success = 0
    middle_skipped_dup: list[tuple[str, str]] = []
    middle_unmatched: dict[str, int] = {}
    middle_orphaned = 0

    for mc in data["middle_categories"]:
        aid = int(mc["aid"])
        old_major_id = int(mc["major_category_id"])
        new_major_id = major_id_map.get(old_major_id)
        if new_major_id is None:
            middle_orphaned += 1
            continue
        user_id = resolve_user(aid)
        if user_id is None:
            label = account_label(aid)
            middle_unmatched[label] = middle_unmatched.get(label, 0) + 1
            continue
        if middle_category_name_exists(new_major_id, mc["name"]):
            middle_skipped_dup.append((account_label(aid), mc["name"]))
            continue
        new_id = _insert_middle_category(user_id, new_major_id, mc["name"], int(mc["display_order"]))
        middle_id_map[int(mc["id"])] = new_id
        middle_success += 1

    knowhow_success = 0
    knowhow_unmatched: dict[str, int] = {}
    knowhow_orphaned = 0

    for k in data["knowhows"]:
        aid = int(k["aid"])
        old_middle_id = k["middle_category_id"]
        new_middle_id: int | None
        if old_middle_id is None:
            new_middle_id = None
        else:
            new_middle_id = middle_id_map.get(int(old_middle_id))
            if new_middle_id is None:
                knowhow_orphaned += 1
                continue
        user_id = resolve_user(aid)
        if user_id is None:
            label = account_label(aid)
            knowhow_unmatched[label] = knowhow_unmatched.get(label, 0) + 1
            continue
        _insert_knowhow(
            user_id,
            new_middle_id,
            str(k["title"]),
            k["keywords"],
            str(k["content"]),
            int(k["display_order"]),
        )
        knowhow_success += 1

    print("=== 大項目 ===", file=sys.stderr)
    print(f"成功: {major_success}件", file=sys.stderr)
    if major_unmatched:
        print("対象外（ユーザ不一致）:", file=sys.stderr)
        for name, count in sorted(major_unmatched.items()):
            print(f"  {name}: {count}件", file=sys.stderr)
    if major_skipped_dup:
        print("スキップ（名称重複）:", file=sys.stderr)
        for name, val in major_skipped_dup:
            print(f"  {name}: {val}", file=sys.stderr)

    print("=== 中項目 ===", file=sys.stderr)
    print(f"成功: {middle_success}件", file=sys.stderr)
    if middle_orphaned:
        print(f"対象外（親大項目が未移行）: {middle_orphaned}件", file=sys.stderr)
    if middle_unmatched:
        print("対象外（ユーザ不一致）:", file=sys.stderr)
        for name, count in sorted(middle_unmatched.items()):
            print(f"  {name}: {count}件", file=sys.stderr)
    if middle_skipped_dup:
        print("スキップ（名称重複）:", file=sys.stderr)
        for name, val in middle_skipped_dup:
            print(f"  {name}: {val}", file=sys.stderr)

    print("=== ノウハウ ===", file=sys.stderr)
    print(f"成功: {knowhow_success}件", file=sys.stderr)
    if knowhow_orphaned:
        print(f"対象外（所属中項目が未移行）: {knowhow_orphaned}件", file=sys.stderr)
    if knowhow_unmatched:
        print("対象外（ユーザ不一致）:", file=sys.stderr)
        for name, count in sorted(knowhow_unmatched.items()):
            print(f"  {name}: {count}件", file=sys.stderr)


if __name__ == "__main__":
    main()
