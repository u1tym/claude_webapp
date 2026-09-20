from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg2
from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from app.config import load_config

# 同時に借りられる接続の上限。上限に達したときは、失敗にせず空くまで待つ。
POOL_MAX = 20

_pool: ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()
_slots = threading.BoundedSemaphore(POOL_MAX)


def connect() -> PgConnection:
    """プールを使わない専用の接続を 1 本開く。呼び出し側が commit / rollback / close する。

    長時間保持する接続（動画の配信）や、移行プログラムのように接続を自分で管理したい場合に使う。
    """
    cfg = load_config()
    return psycopg2.connect(
        host=cfg.db_server,
        dbname=cfg.db_name,
        port=cfg.db_port,
        user=cfg.db_username,
        password=cfg.db_password,
        cursor_factory=RealDictCursor,
    )


def _get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                cfg = load_config()
                _pool = ThreadedConnectionPool(
                    1,
                    POOL_MAX,
                    host=cfg.db_server,
                    dbname=cfg.db_name,
                    port=cfg.db_port,
                    user=cfg.db_username,
                    password=cfg.db_password,
                    cursor_factory=RealDictCursor,
                )
    return _pool


@contextmanager
def get_conn() -> Iterator[PgConnection]:
    """プールから接続を借りる。正常終了で commit、例外で rollback して返す。"""
    _slots.acquire()
    pool = _get_pool()
    conn = pool.getconn()
    discard = False
    try:
        if conn.closed:
            pool.putconn(conn, close=True)
            conn = pool.getconn()
        yield conn
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except psycopg2.Error:
            discard = True
        raise
    finally:
        try:
            pool.putconn(conn, close=discard or bool(conn.closed))
        finally:
            _slots.release()
