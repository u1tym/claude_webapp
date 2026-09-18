from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg2
from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import RealDictCursor

from app.config import load_config


@contextmanager
def get_conn() -> Iterator[PgConnection]:
    cfg = load_config()
    conn = psycopg2.connect(
        host=cfg.db_server,
        dbname=cfg.db_name,
        port=cfg.db_port,
        user=cfg.db_username,
        password=cfg.db_password,
        cursor_factory=RealDictCursor,
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
