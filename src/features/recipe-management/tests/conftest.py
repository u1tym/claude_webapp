from __future__ import annotations

import sys
import uuid
import warnings
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

warnings.filterwarnings("ignore", message=".*httpx.*")

from fastapi.testclient import TestClient  # noqa: E402

from app.config import FEATURE_ID  # noqa: E402
from app.db import get_conn  # noqa: E402
from app.logger import LOG_FILE, close_logging, setup_logging  # noqa: E402
from app.main import app  # noqa: E402
from app.security import COOKIE_NAME  # noqa: E402


@dataclass
class TestUser:
    __test__ = False  # pytest に収集させない

    id: int
    username: str
    client: TestClient


@pytest.fixture(autouse=True)
def log_dir(tmp_path: Path) -> Iterator[Path]:
    directory = tmp_path / "log"
    setup_logging(log_dir=directory)
    yield directory
    close_logging()


def log_text(directory: Path) -> str:
    return (directory / LOG_FILE).read_text(encoding="utf-8")


@pytest.fixture(scope="session", autouse=True)
def feature_row() -> Iterator[None]:
    """機能マスタに本機能が無ければ作る（テスト後に、作ったものだけ消す）。"""
    created = False
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM public.features WHERE id = %s", (FEATURE_ID,))
        if cur.fetchone() is None:
            cur.execute(
                """
                INSERT INTO public.features (id, title, url, icon, icon_media_type)
                VALUES (%s, %s, %s, ''::bytea, 'image/png')
                """,
                (FEATURE_ID, FEATURE_ID, "/portal_recipe_management/"),
            )
            created = True
    yield
    if created:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM public.menu_assignments WHERE feature_id = %s", (FEATURE_ID,))
            cur.execute("DELETE FROM public.features WHERE id = %s", (FEATURE_ID,))


def _delete_user_data(user_id: int) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM recipe_management.recipes WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM recipe_management.ingredients WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM recipe_management.measurements WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM public.sessions WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM public.menu_assignments WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM public.users WHERE id = %s", (user_id,))


@pytest.fixture()
def make_user() -> Iterator[Callable[..., TestUser]]:
    """テスト用ユーザ（セッション付き）を作る。テスト後にデータごと消す。"""
    created: list[int] = []

    def factory(*, assigned: bool = True, deleted: bool = False, expired: bool = False) -> TestUser:
        username = f"rm_test_{uuid.uuid4().hex[:12]}"
        session_id = uuid.uuid4()
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO public.users (username, password_hash, is_deleted) VALUES (%s, 'x', %s) RETURNING id",
                (username, deleted),
            )
            user_id = int(cur.fetchone()["id"])
            created.append(user_id)
            if assigned:
                cur.execute(
                    "INSERT INTO public.menu_assignments (user_id, feature_id, display_order) VALUES (%s, %s, 1)",
                    (user_id, FEATURE_ID),
                )
            expires = datetime.now(timezone.utc) + timedelta(minutes=-5 if expired else 60)
            cur.execute(
                "INSERT INTO public.sessions (id, user_id, expires_at) VALUES (%s, %s, %s)",
                (str(session_id), user_id, expires),
            )
        client = TestClient(app)
        client.cookies.set(COOKIE_NAME, str(session_id))
        return TestUser(id=user_id, username=username, client=client)

    yield factory
    for user_id in created:
        _delete_user_data(user_id)


@pytest.fixture()
def user(make_user: Callable[..., TestUser]) -> TestUser:
    return make_user()


@pytest.fixture()
def other_user(make_user: Callable[..., TestUser]) -> TestUser:
    return make_user()
