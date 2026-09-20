"""別サーバで稼働する knowhow（旧ノウハウ管理サービス）から、未削除の大項目・中項目・
ノウハウとアカウント一覧を JSON へエクスポートするスクリプト。

このスクリプトは旧サーバ側（または旧サーバの DB に到達できる環境）で実行する。

使い方:
    python export_from_knowhow.py \
        --host localhost --port 5432 --dbname <旧DB名> \
        --user <旧DBユーザ> --password <旧DBパスワード> \
        --output knowhow_export.json

接続情報は環境変数でも指定できる（引数が優先）:
    KNOWHOW_DB_HOST, KNOWHOW_DB_PORT, KNOWHOW_DB_NAME, KNOWHOW_DB_USER, KNOWHOW_DB_PASSWORD
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class ConnectionArgs:
    host: str
    port: int
    dbname: str
    user: str
    password: str


def _parse_args() -> tuple[ConnectionArgs, str]:
    parser = argparse.ArgumentParser(description="knowhow から未削除データを JSON へエクスポートする")
    parser.add_argument("--host", default=os.environ.get("KNOWHOW_DB_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("KNOWHOW_DB_PORT", "5432")))
    parser.add_argument("--dbname", default=os.environ.get("KNOWHOW_DB_NAME", ""))
    parser.add_argument("--user", default=os.environ.get("KNOWHOW_DB_USER", ""))
    parser.add_argument("--password", default=os.environ.get("KNOWHOW_DB_PASSWORD", ""))
    parser.add_argument("--output", required=True, help="出力先の JSON ファイルパス")
    args = parser.parse_args()
    return (
        ConnectionArgs(
            host=args.host,
            port=args.port,
            dbname=args.dbname,
            user=args.user,
            password=args.password,
        ),
        args.output,
    )


def main() -> None:
    conn_args, output_path = _parse_args()

    import psycopg2
    from psycopg2.extras import RealDictCursor

    conn = psycopg2.connect(
        host=conn_args.host,
        port=conn_args.port,
        dbname=conn_args.dbname,
        user=conn_args.user,
        password=conn_args.password,
        cursor_factory=RealDictCursor,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, username FROM public.accounts")
            accounts = [{"id": int(row["id"]), "username": str(row["username"])} for row in cur.fetchall()]

            cur.execute(
                """
                SELECT id, aid, name, display_order
                FROM public.major_categories
                WHERE is_deleted = false
                ORDER BY id ASC
                """
            )
            major_categories = [
                {
                    "id": int(row["id"]),
                    "aid": int(row["aid"]),
                    "name": str(row["name"]),
                    "display_order": int(row["display_order"]),
                }
                for row in cur.fetchall()
            ]

            cur.execute(
                """
                SELECT id, aid, major_category_id, name, display_order
                FROM public.middle_categories
                WHERE is_deleted = false
                ORDER BY id ASC
                """
            )
            middle_categories = [
                {
                    "id": int(row["id"]),
                    "aid": int(row["aid"]),
                    "major_category_id": int(row["major_category_id"]),
                    "name": str(row["name"]),
                    "display_order": int(row["display_order"]),
                }
                for row in cur.fetchall()
            ]

            cur.execute(
                """
                SELECT id, aid, middle_category_id, title, keywords, content, display_order
                FROM public.knowhows
                WHERE is_deleted = false
                ORDER BY id ASC
                """
            )
            knowhows = [
                {
                    "id": int(row["id"]),
                    "aid": int(row["aid"]),
                    "middle_category_id": (
                        None if row["middle_category_id"] is None else int(row["middle_category_id"])
                    ),
                    "title": str(row["title"]),
                    "keywords": (None if row["keywords"] is None else str(row["keywords"])),
                    "content": str(row["content"]),
                    "display_order": int(row["display_order"]),
                }
                for row in cur.fetchall()
            ]
    finally:
        conn.close()

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "accounts": accounts,
                "major_categories": major_categories,
                "middle_categories": middle_categories,
                "knowhows": knowhows,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(
        f"アカウント: {len(accounts)}件、大項目: {len(major_categories)}件、"
        f"中項目: {len(middle_categories)}件、ノウハウ: {len(knowhows)}件を {output_path} へ出力しました",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
