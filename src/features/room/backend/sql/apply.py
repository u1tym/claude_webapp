from __future__ import annotations

import sys
from pathlib import Path

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import load_config  # noqa: E402

SQL_DIR = Path(__file__).resolve().parent
DDL_PATHS = sorted(SQL_DIR.glob("*.sql"))


def create_schema(admin_user: str, admin_password: str) -> None:
    """管理者でスキーマ room を作り、アプリ用ユーザへ権限を渡す。"""
    cfg = load_config()
    conn = psycopg2.connect(
        host=cfg.db_server,
        dbname=cfg.db_name,
        port=cfg.db_port,
        user=admin_user,
        password=admin_password,
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f'CREATE SCHEMA IF NOT EXISTS room AUTHORIZATION "{cfg.db_username}"'
            )
            cur.execute(f'GRANT ALL ON SCHEMA room TO "{cfg.db_username}"')
    finally:
        conn.close()


def apply_ddl() -> None:
    """DDL を適用する（繰り返し適用しても壊れない）。"""
    cfg = load_config()
    conn = psycopg2.connect(
        host=cfg.db_server,
        dbname=cfg.db_name,
        port=cfg.db_port,
        user=cfg.db_username,
        password=cfg.db_password,
    )
    try:
        with conn.cursor() as cur:
            for path in DDL_PATHS:
                cur.execute(path.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    # 開発用 DB の管理者（rules/13-db.md）
    create_schema("postgres", "postgres")
    apply_ddl()
    print("applied")


if __name__ == "__main__":
    main()
