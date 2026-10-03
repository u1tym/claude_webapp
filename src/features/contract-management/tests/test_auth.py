"""認証・認可のテスト（Cookie、DEBUG_USER、API キー / api-design.md 認証、api-key-management の REQ-006〜REQ-008）。

データを返すエンドポイントとして GET /categories を使う（Cookie と API キーの両方を受け付ける）。
"""

from __future__ import annotations

import secrets
import uuid
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import FEATURE_ID, load_config
from conftest import Owner, bearer, execute, issue_key

PATH = "/categories"


def _expires_at(owner: Owner) -> datetime:
    return execute("SELECT expires_at FROM public.sessions WHERE id = %s", (owner.session_id,))[0]["expires_at"]  # type: ignore[return-value]


def _last_used(key_id: int) -> object:
    return execute("SELECT last_used_at FROM public.api_keys WHERE id = %s", (key_id,))[0]["last_used_at"]


# ---- Cookie ----


def test_valid_cookie(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    assert make_client(make_owner()).get(PATH).status_code == 200


def test_no_cookie_is_401(client: TestClient) -> None:
    res = client.get(PATH)
    assert res.status_code == 401 and res.json() == {"detail": "未ログイン"}


def test_invalid_cookie_values_are_401(client: TestClient) -> None:
    client.cookies.set("session_id", "not-a-uuid")
    assert client.get(PATH).status_code == 401
    client.cookies.set("session_id", str(uuid.uuid4()))  # 行が無い
    assert client.get(PATH).status_code == 401


def test_expired_session_is_401(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    owner = make_owner()
    execute("UPDATE public.sessions SET expires_at = %s WHERE id = %s", (datetime.now(timezone.utc) - timedelta(seconds=1), owner.session_id))
    assert make_client(owner).get(PATH).status_code == 401


def test_deleted_user_is_401(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    owner = make_owner()
    execute("UPDATE public.users SET is_deleted = true WHERE id = %s", (owner.id,))
    assert make_client(owner).get(PATH).status_code == 401


def test_unassigned_user_is_403(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    owner = make_owner(assigned=False)
    res = make_client(owner).get(PATH)
    assert res.status_code == 403 and res.json() == {"detail": "権限がありません"}


@pytest.fixture()
def feature_deleted() -> Iterator[None]:
    execute("UPDATE public.features SET is_deleted = true WHERE id = %s", (FEATURE_ID,))
    try:
        yield
    finally:
        execute("UPDATE public.features SET is_deleted = false WHERE id = %s", (FEATURE_ID,))


def test_deleted_feature_is_403(
    make_owner: Callable[..., Owner], make_client: Callable[..., TestClient], feature_deleted: None
) -> None:
    assert make_client(make_owner()).get(PATH).status_code == 403


def test_session_expiry_is_extended_on_cookie_access(
    make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]
) -> None:
    owner = make_owner()
    execute("UPDATE public.sessions SET expires_at = %s WHERE id = %s", (datetime.now(timezone.utc) + timedelta(minutes=1), owner.session_id))
    before = _expires_at(owner)
    assert make_client(owner).get(PATH).status_code == 200
    assert _expires_at(owner) > before + timedelta(minutes=10)


def test_settings_needs_no_auth(client: TestClient) -> None:
    res = client.get("/settings")
    assert res.status_code == 200 and set(res.json()) == {"login_url", "menu_url", "icon_system", "icon_back"}
    # API キーのヘッダがあっても、判定しない
    assert client.get("/settings", headers={"Authorization": "Bearer wak_invalid"}).status_code == 200


# ---- DEBUG_USER ----


def _debug(monkeypatch: pytest.MonkeyPatch, name: str | None) -> TestClient:
    from app.main import app

    patched = replace(load_config(), debug_user=name)
    monkeypatch.setattr("app.deps.load_config", lambda: patched)
    return TestClient(app)


def test_debug_user_works_without_cookie(make_owner: Callable[..., Owner], monkeypatch: pytest.MonkeyPatch) -> None:
    owner = make_owner()
    assert _debug(monkeypatch, owner.username).get(PATH).status_code == 200


def test_debug_user_unknown_or_deleted_is_401(make_owner: Callable[..., Owner], monkeypatch: pytest.MonkeyPatch) -> None:
    assert _debug(monkeypatch, "no_such_user_" + uuid.uuid4().hex).get(PATH).status_code == 401
    owner = make_owner()
    execute("UPDATE public.users SET is_deleted = true WHERE id = %s", (owner.id,))
    assert _debug(monkeypatch, owner.username).get(PATH).status_code == 401


def test_debug_user_still_needs_assignment(make_owner: Callable[..., Owner], monkeypatch: pytest.MonkeyPatch) -> None:
    owner = make_owner(assigned=False)
    assert _debug(monkeypatch, owner.username).get(PATH).status_code == 403


# ---- API キー ----


def test_valid_key_allows_access_and_updates_last_used(
    make_owner: Callable[..., Owner], client: TestClient
) -> None:
    key = issue_key(make_owner())
    assert _last_used(key.id) is None
    assert client.get(PATH, headers=bearer(key)).status_code == 200
    assert _last_used(key.id) is not None


def test_key_scheme_is_case_insensitive_and_trimmed(make_owner: Callable[..., Owner], client: TestClient) -> None:
    key = issue_key(make_owner())
    assert client.get(PATH, headers={"Authorization": f"bearer {key.key}"}).status_code == 200
    assert client.get(PATH, headers={"Authorization": f"BEARER   {key.key}  "}).status_code == 200


@pytest.mark.parametrize("case", ["unknown", "revoked", "expired", "deleted_owner", "not_bearer", "empty", "basic"])
def test_invalid_key_is_401(make_owner: Callable[..., Owner], client: TestClient, case: str) -> None:
    owner = make_owner()
    if case == "unknown":
        headers = {"Authorization": "Bearer wak_" + secrets.token_urlsafe(32)}
    elif case == "revoked":
        headers = bearer(issue_key(owner, revoked=True))
    elif case == "expired":
        headers = bearer(issue_key(owner, expires_in=timedelta(minutes=-1)))
    elif case == "deleted_owner":
        key = issue_key(owner)
        execute("UPDATE public.users SET is_deleted = true WHERE id = %s", (owner.id,))
        headers = bearer(key)
    elif case == "not_bearer":
        headers = {"Authorization": "wak_" + secrets.token_urlsafe(32)}
    elif case == "basic":
        headers = {"Authorization": "Basic dXNlcjpwYXNz"}
    else:
        headers = {"Authorization": "Bearer "}
    res = client.get(PATH, headers=headers)
    assert res.status_code == 401 and res.json() == {"detail": "未ログイン"}


def test_key_of_unassigned_owner_is_403_and_not_marked_used(make_owner: Callable[..., Owner], client: TestClient) -> None:
    key = issue_key(make_owner(assigned=False))
    res = client.get(PATH, headers=bearer(key))
    assert res.status_code == 403 and res.json() == {"detail": "権限がありません"}
    assert _last_used(key.id) is None


def test_invalid_key_does_not_fall_back_to_cookie(
    make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]
) -> None:
    owner = make_owner()
    c = make_client(owner)
    assert c.get(PATH).status_code == 200  # Cookie だけなら通る
    assert c.get(PATH, headers={"Authorization": "Bearer wak_invalid"}).status_code == 401


def test_invalid_key_does_not_fall_back_to_debug_user(make_owner: Callable[..., Owner], monkeypatch: pytest.MonkeyPatch) -> None:
    owner = make_owner()
    c = _debug(monkeypatch, owner.username)
    assert c.get(PATH).status_code == 200
    assert c.get(PATH, headers={"Authorization": "Bearer wak_invalid"}).status_code == 401


def test_key_access_does_not_extend_session(make_owner: Callable[..., Owner], client: TestClient) -> None:
    owner = make_owner()
    execute("UPDATE public.sessions SET expires_at = %s WHERE id = %s", (datetime.now(timezone.utc) + timedelta(minutes=1), owner.session_id))
    before = _expires_at(owner)
    assert client.get(PATH, headers=bearer(issue_key(owner))).status_code == 200
    assert _expires_at(owner) == before


def test_key_acts_as_its_owner(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient], client: TestClient) -> None:
    a = make_owner()
    b = make_owner()
    make_client(a).post(PATH, json={"name": "Aの区分"})
    make_client(b).post(PATH, json={"name": "Bの区分"})
    names = [i["name"] for i in client.get(PATH, headers=bearer(issue_key(a))).json()["items"]]
    assert "Aの区分" in names and "Bの区分" not in names
