"""contract-management のテスト共通部品。開発用 DB（tstdb）に、テスト用のユーザ・セッション・割当・API キーを作り、後始末する。"""

from __future__ import annotations

import hashlib
import secrets
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
from app.logger import close_logging, setup_logging  # noqa: E402


@dataclass(frozen=True)
class Owner:
    id: int
    username: str
    session_id: str


@dataclass(frozen=True)
class IssuedKey:
    id: int
    key: str


def execute(sql: str, params: tuple[object, ...] = ()) -> list[dict[str, object]]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()] if cur.description else []


def assign_feature(user_id: int) -> None:
    execute(
        """
        INSERT INTO public.features (id, title, url, icon, icon_media_type)
        VALUES (%s, %s, %s, ''::bytea, '')
        ON CONFLICT (id) DO NOTHING
        """,
        (FEATURE_ID, FEATURE_ID, f"/portal_{FEATURE_ID.replace('-', '_')}/"),
    )
    execute(
        "INSERT INTO public.menu_assignments (user_id, feature_id, display_order) VALUES (%s, %s, 1) "
        "ON CONFLICT DO NOTHING",
        (user_id, FEATURE_ID),
    )


def insert_category(owner: Owner, name: str, is_financial: bool = False) -> int:
    return int(
        execute(
            "INSERT INTO contract_management.categories (user_id, name, is_financial) VALUES (%s, %s, %s) RETURNING id",
            (owner.id, name, is_financial),
        )[0]["id"]
    )


def insert_contract(owner: Owner, category_id: int, name: str, **cols: object) -> int:
    """契約の行を、API を通さずに直接入れる（列名で指定。password の値もここでは指定できる）。"""
    cols = {"user_id": owner.id, "category_id": category_id, "name": name, **cols}
    keys = ", ".join(cols)
    marks = ", ".join(["%s"] * len(cols))
    return int(
        execute(
            f"INSERT INTO contract_management.contracts ({keys}) VALUES ({marks}) RETURNING id",
            tuple(cols.values()),
        )[0]["id"]
    )


def _cleanup(user_ids: list[int]) -> None:
    """本機能のデータを、参照の順に消す。ユーザ行は、他のテストと同じく残す。"""
    execute("DELETE FROM contract_management.cancellation_plan WHERE user_id = ANY(%s)", (user_ids,))
    execute(
        "DELETE FROM contract_management.contract_dependencies WHERE contract_id IN "
        "(SELECT id FROM contract_management.contracts WHERE user_id = ANY(%s))",
        (user_ids,),
    )
    execute(
        "UPDATE contract_management.contracts SET payment_contract_id = NULL WHERE user_id = ANY(%s)",
        (user_ids,),
    )
    execute("DELETE FROM contract_management.contracts WHERE user_id = ANY(%s)", (user_ids,))
    execute("DELETE FROM contract_management.categories WHERE user_id = ANY(%s)", (user_ids,))
    execute("DELETE FROM public.api_keys WHERE user_id = ANY(%s)", (user_ids,))
    execute("DELETE FROM public.sessions WHERE user_id = ANY(%s)", (user_ids,))
    execute("DELETE FROM public.menu_assignments WHERE user_id = ANY(%s)", (user_ids,))


@pytest.fixture()
def make_owner() -> Iterator[Callable[..., Owner]]:
    created: list[int] = []

    def factory(assigned: bool = True) -> Owner:
        username = f"contract_test_{uuid.uuid4().hex[:12]}"
        user_id = int(
            execute(
                "INSERT INTO public.users (username, password_hash) VALUES (%s, 'x') RETURNING id",
                (username,),
            )[0]["id"]
        )
        created.append(user_id)
        if assigned:
            assign_feature(user_id)
        session_id = str(uuid.uuid4())
        execute(
            "INSERT INTO public.sessions (id, user_id, expires_at) VALUES (%s, %s, %s)",
            (session_id, user_id, datetime.now(timezone.utc) + timedelta(minutes=30)),
        )
        return Owner(id=user_id, username=username, session_id=session_id)

    yield factory
    if created:
        _cleanup(created)


def issue_key(owner: Owner, expires_in: timedelta | None = None, revoked: bool = False) -> IssuedKey:
    key = "wak_" + secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    row = execute(
        """
        INSERT INTO public.api_keys (user_id, name, key_hash, key_prefix, created_at, expires_at, revoked_at)
        VALUES (%s, 'test', %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            owner.id,
            hashlib.sha256(key.encode()).hexdigest(),
            key[:12],
            now - timedelta(days=2),
            now + expires_in if expires_in is not None else None,
            now if revoked else None,
        ),
    )[0]
    return IssuedKey(id=int(row["id"]), key=key)


def bearer(key: IssuedKey) -> dict[str, str]:
    return {"Authorization": f"Bearer {key.key}"}


@pytest.fixture(autouse=True)
def log_dir(tmp_path: Path) -> Iterator[Path]:
    directory = tmp_path / "log"
    setup_logging(log_dir=directory)
    yield directory
    close_logging()


@pytest.fixture()
def make_client(monkeypatch: pytest.MonkeyPatch) -> Callable[..., TestClient]:
    """Cookie（セッション ID）を持つクライアントを作る。owner を渡さなければ Cookie なし。"""
    from app.main import app

    patched = replace(load_config(), debug_user=None)
    monkeypatch.setattr("app.deps.load_config", lambda: patched)

    def factory(owner: Owner | None = None) -> TestClient:
        client = TestClient(app)
        if owner is not None:
            client.cookies.set("session_id", owner.session_id)
        return client

    return factory


@pytest.fixture()
def client(make_client: Callable[..., TestClient]) -> TestClient:
    """Cookie も API キーも持たないクライアント。"""
    return make_client()
