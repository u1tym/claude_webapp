from __future__ import annotations

import sys
from pathlib import Path

import psycopg2

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import load_config  # noqa: E402

SQL_DIR = Path(__file__).resolve().parent
DDL_PATHS = sorted(SQL_DIR.glob("*.sql"))


def apply_ddl() -> None:
    """`backend/.env` の接続で DDL を適用する。`portal` の DDL（public.users）を前提とする。"""
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
    apply_ddl()
    print("applied")


if __name__ == "__main__":
    main()
