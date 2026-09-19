"""別サーバで稼働する psinfo（旧パスワード管理サービス）から、未削除のパスワードエントリと
アカウント一覧を JSON へエクスポートするスクリプト。

このスクリプトは旧サーバ側（または旧サーバの DB に到達できる環境）で実行する。
パスワードの値は標準出力・ログのいずれにも出力しない（出力先は指定した JSON ファイルのみ）。

使い方:
    python export_from_psinfo.py \
        --host localhost --port 5432 --dbname tamtdb \
        --user tamtuser --password TAMTTAMT \
        --output psinfo_export.json

接続情報は環境変数でも指定できる（引数が優先）:
    PSINFO_DB_HOST, PSINFO_DB_PORT, PSINFO_DB_NAME, PSINFO_DB_USER, PSINFO_DB_PASSWORD
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
    parser = argparse.ArgumentParser(description="psinfo から未削除エントリを JSON へエクスポートする")
    parser.add_argument("--host", default=os.environ.get("PSINFO_DB_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PSINFO_DB_PORT", "5432")))
    parser.add_argument("--dbname", default=os.environ.get("PSINFO_DB_NAME", "tamtdb"))
    parser.add_argument("--user", default=os.environ.get("PSINFO_DB_USER", "tamtuser"))
    parser.add_argument("--password", default=os.environ.get("PSINFO_DB_PASSWORD", ""))
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

    # psycopg2 は旧サーバ側の実行環境に依存するため、ここで遅延 import する。
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
                SELECT aid, title, userword, psword, site, memo
                FROM psinfo.master
                WHERE deleted_count = 0
                ORDER BY id ASC
                """
            )
            entries = [
                {
                    "aid": int(row["aid"]),
                    "title": str(row["title"]),
                    "userword": str(row["userword"]),
                    "psword": str(row["psword"]),
                    "site": (None if row["site"] is None else str(row["site"])),
                    "memo": (None if row["memo"] is None else str(row["memo"])),
                }
                for row in cur.fetchall()
            ]
    finally:
        conn.close()

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"accounts": accounts, "entries": entries}, f, ensure_ascii=False, indent=2)

    # パスワードの値は出力しない。件数だけを知らせる。
    print(f"アカウント: {len(accounts)}件、パスワードエントリ: {len(entries)}件を {output_path} へ出力しました", file=sys.stderr)


if __name__ == "__main__":
    main()
