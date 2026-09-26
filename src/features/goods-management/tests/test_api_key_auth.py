"""API キー（Authorization: Bearer）による認証のテスト（api-key-management の REQ-006〜REQ-008）。"""

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
from app.logger import LOG_FILE, close_logging, setup_logging  # noqa: E402

# 一覧と登録に使う、本人のデータだけを扱うエンドポイント
DATA_PATH = "/persons"
NAME_FIELD = "name"


def _payload() -> dict[str, str]:
    return {"name": f"api-key-{uuid.uuid4().hex[:8]}"}


@dataclass(frozen=True)
class Owner:
    id: int
    username: str
    session_id: str


@dataclass(frozen=True)
class IssuedKey:
    id: int
    key: str


def _execute(sql: str, params: tuple[object, ...]) -> list[dict[str, object]]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()] if cur.description else []


def _assign(user_id: int) -> None:
    _execute(
        """
        INSERT INTO public.features (id, title, url, icon, icon_media_type)
        VALUES (%s, %s, %s, ''::bytea, '')
        ON CONFLICT (id) DO NOTHING
        """,
        (FEATURE_ID, FEATURE_ID, f"/portal_{FEATURE_ID.replace('-', '_')}/"),
    )
    _execute(
        "INSERT INTO public.menu_assignments (user_id, feature_id, display_order) VALUES (%s, %s, 1) "
        "ON CONFLICT DO NOTHING",
        (user_id, FEATURE_ID),
    )


@pytest.fixture()
def make_owner() -> Iterator[Callable[..., Owner]]:
    created: list[int] = []

    def factory(assigned: bool = True) -> Owner:
        username = f"apikey_test_{uuid.uuid4().hex[:12]}"
        user_id = int(
            _execute(
                "INSERT INTO public.users (username, password_hash) VALUES (%s, 'x') RETURNING id",
                (username,),
            )[0]["id"]
        )
        created.append(user_id)
        if assigned:
            _assign(user_id)
        session_id = str(uuid.uuid4())
        _execute(
            "INSERT INTO public.sessions (id, user_id, expires_at) VALUES (%s, %s, %s)",
            (session_id, user_id, datetime.now(timezone.utc) + timedelta(minutes=30)),
        )
        return Owner(id=user_id, username=username, session_id=session_id)

    yield factory
    if created:
        # 業務データの行が user_id を参照するため、ユーザ行は既存のテストと同じく残す
        _execute("DELETE FROM public.api_keys WHERE user_id = ANY(%s)", (created,))
        _execute("DELETE FROM public.sessions WHERE user_id = ANY(%s)", (created,))
        _execute("DELETE FROM public.menu_assignments WHERE user_id = ANY(%s)", (created,))


def issue_key(owner: Owner, expires_in: timedelta | None = None, revoked: bool = False) -> IssuedKey:
    key = "wak_" + secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    row = _execute(
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


def last_used_at(key: IssuedKey) -> object:
    return _execute("SELECT last_used_at FROM public.api_keys WHERE id = %s", (key.id,))[0]["last_used_at"]


def bearer(key: IssuedKey) -> dict[str, str]:
    return {"Authorization": f"Bearer {key.key}"}


@pytest.fixture(autouse=True)
def log_dir(tmp_path: Path) -> Iterator[Path]:
    directory = tmp_path / "log"
    setup_logging(log_dir=directory)
    yield directory
    close_logging()


def _client(monkeypatch: pytest.MonkeyPatch, debug_user: str | None = None) -> TestClient:
    from app.main import app

    patched = replace(load_config(), debug_user=debug_user)
    monkeypatch.setattr("app.deps.load_config", lambda: patched)
    return TestClient(app)


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    return _client(monkeypatch)


def test_valid_key_allows_access_to_own_data(client: TestClient, make_owner: Callable[..., Owner]) -> None:
    owner = make_owner()
    other = make_owner()
    key = issue_key(owner)

    created = client.post(DATA_PATH, json=_payload(), headers=bearer(key))
    assert created.status_code == 201
    client.cookies.set("session_id", other.session_id)
    others = client.post(DATA_PATH, json=_payload())
    assert others.status_code == 201
    client.cookies.clear()

    res = client.get(DATA_PATH, headers=bearer(key))
    assert res.status_code == 200
    names = [item[NAME_FIELD] for item in res.json()["items"]]
    assert created.json()[NAME_FIELD] in names
    assert others.json()[NAME_FIELD] not in names


def test_last_used_at_updated_only_when_allowed(
    client: TestClient, make_owner: Callable[..., Owner]
) -> None:
    owner = make_owner()
    key = issue_key(owner)
    assert last_used_at(key) is None
    assert client.get(DATA_PATH, headers=bearer(key)).status_code == 200
    assert last_used_at(key) is not None

    unassigned = make_owner(assigned=False)
    denied = issue_key(unassigned)
    assert client.get(DATA_PATH, headers=bearer(denied)).status_code == 403
    assert last_used_at(denied) is None


@pytest.mark.parametrize(
    "case",
    ["unknown", "revoked", "expired", "deleted_owner", "not_bearer", "empty"],
)
def test_invalid_key_is_401(client: TestClient, make_owner: Callable[..., Owner], case: str) -> None:
    owner = make_owner()
    if case == "unknown":
        headers = {"Authorization": "Bearer wak_" + secrets.token_urlsafe(32)}
    elif case == "revoked":
        headers = bearer(issue_key(owner, revoked=True))
    elif case == "expired":
        headers = bearer(issue_key(owner, expires_in=timedelta(minutes=-1)))
    elif case == "deleted_owner":
        key = issue_key(owner)
        _execute("UPDATE public.users SET is_deleted = true WHERE id = %s", (owner.id,))
        headers = bearer(key)
    elif case == "not_bearer":
        headers = {"Authorization": f"Basic {issue_key(owner).key}"}
    else:
        headers = {"Authorization": "Bearer "}

    res = client.get(DATA_PATH, headers=headers)
    assert res.status_code == 401
    assert res.json() == {"detail": "未ログイン"}
    assert res.headers.get("www-authenticate") == "Bearer"


def test_unassigned_owner_is_403(client: TestClient, make_owner: Callable[..., Owner]) -> None:
    owner = make_owner(assigned=False)
    res = client.get(DATA_PATH, headers=bearer(issue_key(owner)))
    assert res.status_code == 403
    assert res.json() == {"detail": "権限がありません"}


def test_invalid_key_does_not_fall_back_to_cookie(
    client: TestClient, make_owner: Callable[..., Owner]
) -> None:
    owner = make_owner()
    client.cookies.set("session_id", owner.session_id)
    assert client.get(DATA_PATH).status_code == 200
    res = client.get(DATA_PATH, headers={"Authorization": "Bearer wak_invalid"})
    assert res.status_code == 401


def test_invalid_key_does_not_fall_back_to_debug_user(
    monkeypatch: pytest.MonkeyPatch, make_owner: Callable[..., Owner]
) -> None:
    owner = make_owner()
    client = _client(monkeypatch, debug_user=owner.username)
    assert client.get(DATA_PATH).status_code == 200
    assert client.get(DATA_PATH, headers={"Authorization": "Bearer wak_invalid"}).status_code == 401


def test_cookie_only_access_unchanged(client: TestClient, make_owner: Callable[..., Owner]) -> None:
    owner = make_owner()
    assert client.get(DATA_PATH).status_code == 401
    client.cookies.set("session_id", owner.session_id)
    assert client.get(DATA_PATH).status_code == 200


def test_settings_ignores_authorization(client: TestClient) -> None:
    res = client.get("/settings", headers={"Authorization": "Bearer wak_invalid"})
    assert res.status_code == 200


def test_log_records_decision_without_key(
    client: TestClient, make_owner: Callable[..., Owner], log_dir: Path
) -> None:
    owner = make_owner()
    key = issue_key(owner)
    revoked = issue_key(owner, revoked=True)
    client.get(DATA_PATH, headers=bearer(key))
    client.get(DATA_PATH, headers=bearer(revoked))

    text = (log_dir / LOG_FILE).read_text(encoding="utf-8")
    assert f"API キー認証成功 username={owner.username} id={key.id} prefix={key.key[:12]}" in text
    assert f"API キー認証失敗 id={revoked.id} prefix={revoked.key[:12]} 理由=失効済み" in text
    for secret in (key.key, revoked.key, hashlib.sha256(key.key.encode()).hexdigest()):
        assert secret not in text
