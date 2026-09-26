from __future__ import annotations

import sys
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402

from app.config import FEATURE_ID, load_config  # noqa: E402
from app.db import get_conn  # noqa: E402
from app.logger import LOG_FILE, close_logging, setup_logging  # noqa: E402


@dataclass(frozen=True)
class AppUser:
    id: int
    username: str
    session_id: str


def _create_user(username: str) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO public.users (username, password_hash) VALUES (%s, 'x') RETURNING id",
                (username,),
            )
            row = cur.fetchone()
            assert row is not None
            return int(row["id"])


def _create_session(user_id: int) -> str:
    session_id = str(uuid.uuid4())
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO public.sessions (id, user_id, expires_at) VALUES (%s, %s, %s)",
                (session_id, user_id, datetime.now(timezone.utc) + timedelta(minutes=30)),
            )
    return session_id


def assign(user_id: int, feature_id: str = FEATURE_ID) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.features (id, title, url, icon, icon_media_type)
                VALUES (%s, %s, %s, ''::bytea, '')
                ON CONFLICT (id) DO NOTHING
                """,
                (feature_id, feature_id, f"/portal_{feature_id.replace('-', '_')}/"),
            )
            cur.execute(
                """
                INSERT INTO public.menu_assignments (user_id, feature_id, display_order)
                VALUES (%s, %s, 1)
                ON CONFLICT DO NOTHING
                """,
                (user_id, feature_id),
            )


def set_user_deleted(user_id: int, deleted: bool) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE public.users SET is_deleted = %s WHERE id = %s", (deleted, user_id))


def db_rows(sql: str, params: tuple[object, ...]) -> list[dict[str, object]]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def _cleanup(user_ids: list[int]) -> None:
    if not user_ids:
        return
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM public.api_keys WHERE user_id = ANY(%s)", (user_ids,))
            cur.execute("DELETE FROM public.sessions WHERE user_id = ANY(%s)", (user_ids,))
            cur.execute("DELETE FROM public.menu_assignments WHERE user_id = ANY(%s)", (user_ids,))
            cur.execute("DELETE FROM public.users WHERE id = ANY(%s)", (user_ids,))


@pytest.fixture()
def make_user() -> Iterator[Callable[..., AppUser]]:
    created: list[int] = []

    def factory(assigned: bool = True) -> AppUser:
        username = f"akm_test_{uuid.uuid4().hex[:12]}"
        user_id = _create_user(username)
        created.append(user_id)
        if assigned:
            assign(user_id)
        return AppUser(id=user_id, username=username, session_id=_create_session(user_id))

    yield factory
    _cleanup(created)


@pytest.fixture(autouse=True)
def log_dir(tmp_path: Path) -> Iterator[Path]:
    directory = tmp_path / "log"
    setup_logging(log_dir=directory)
    yield directory
    close_logging()


def log_text(directory: Path) -> str:
    return (directory / LOG_FILE).read_text(encoding="utf-8")


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """DEBUG_USER を空にして、Cookie による認証で動かすクライアント。"""
    from app.main import app

    patched = replace(load_config(), debug_user=None)
    monkeypatch.setattr("app.deps.load_config", lambda: patched)
    return TestClient(app)


def login(client: TestClient, user: AppUser) -> TestClient:
    client.cookies.set("session_id", user.session_id)
    return client
