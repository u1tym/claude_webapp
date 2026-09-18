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


def _create_role_and_db(admin_user: str, admin_password: str) -> None:
    cfg = load_config()
    conn = psycopg2.connect(
        host=cfg.db_server,
        dbname="postgres",
        port=cfg.db_port,
        user=admin_user,
        password=admin_password,
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (cfg.db_username,))
            if cur.fetchone() is None:
                cur.execute(
                    f'CREATE USER "{cfg.db_username}" LOGIN PASSWORD %s',
                    (cfg.db_password,),
                )
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (cfg.db_name,))
            if cur.fetchone() is None:
                cur.execute(
                    f'CREATE DATABASE "{cfg.db_name}" OWNER "{cfg.db_username}" '
                    "ENCODING 'UTF8' TEMPLATE template1"
                )
        grant = psycopg2.connect(
            host=cfg.db_server,
            dbname=cfg.db_name,
            port=cfg.db_port,
            user=admin_user,
            password=admin_password,
        )
        grant.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        try:
            with grant.cursor() as cur:
                cur.execute(f'GRANT ALL ON SCHEMA public TO "{cfg.db_username}"')
                cur.execute(f'ALTER SCHEMA public OWNER TO "{cfg.db_username}"')
        finally:
            grant.close()
    finally:
        conn.close()


def apply_ddl() -> None:
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
    _create_role_and_db("postgres", "postgres")
    apply_ddl()
    print("applied")


if __name__ == "__main__":
    main()
