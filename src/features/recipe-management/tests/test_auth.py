from __future__ import annotations

import dataclasses
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.config import load_config
from app.db import get_conn
from app.main import app

from conftest import TestUser, log_text


def test_settings_needs_no_login() -> None:
    res = TestClient(app).get("/settings")
    assert res.status_code == 200
    body = res.json()
    assert set(body) == {"login_url", "menu_url", "icon_system", "icon_back"}


def test_unauthenticated_is_401() -> None:
    res = TestClient(app).get("/ingredients")
    assert res.status_code == 401
    assert res.json() == {"detail": "未ログイン"}


def test_broken_cookie_is_401() -> None:
    client = TestClient(app)
    client.cookies.set("session_id", "not-a-uuid")
    assert client.get("/ingredients").status_code == 401


def test_expired_session_is_401(make_user: Callable[..., TestUser]) -> None:
    assert make_user(expired=True).client.get("/ingredients").status_code == 401


def test_deleted_user_is_401(make_user: Callable[..., TestUser]) -> None:
    assert make_user(deleted=True).client.get("/ingredients").status_code == 401


def test_unassigned_user_is_403(make_user: Callable[..., TestUser]) -> None:
    res = make_user(assigned=False).client.get("/ingredients")
    assert res.status_code == 403
    assert res.json() == {"detail": "権限がありません"}


def test_deleted_feature_is_403(user: TestUser) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE public.features SET is_deleted = true WHERE id = 'recipe-management'")
    try:
        assert user.client.get("/ingredients").status_code == 403
    finally:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("UPDATE public.features SET is_deleted = false WHERE id = 'recipe-management'")


def test_session_expiry_is_extended(user: TestUser) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE public.sessions SET expires_at = now() + interval '1 minute' WHERE user_id = %s",
            (user.id,),
        )
    assert user.client.get("/ingredients").status_code == 200
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT expires_at > now() + interval '30 minutes' AS extended FROM public.sessions WHERE user_id = %s",
            (user.id,),
        )
        assert cur.fetchone()["extended"] is True


def test_session_id_is_not_logged(user: TestUser, log_dir) -> None:
    session_id = user.client.cookies.get("session_id")
    assert session_id
    user.client.get("/ingredients")
    TestClient(app).get("/ingredients")
    assert session_id not in log_text(log_dir)


def test_debug_user_skips_cookie_but_checks_assignment(
    monkeypatch: pytest.MonkeyPatch, make_user: Callable[..., TestUser]
) -> None:
    allowed = make_user()
    denied = make_user(assigned=False)
    real = load_config()

    monkeypatch.setattr("app.deps.load_config", lambda: dataclasses.replace(real, debug_user=allowed.username))
    assert TestClient(app).get("/ingredients").status_code == 200

    monkeypatch.setattr("app.deps.load_config", lambda: dataclasses.replace(real, debug_user=denied.username))
    assert TestClient(app).get("/ingredients").status_code == 403

    monkeypatch.setattr("app.deps.load_config", lambda: dataclasses.replace(real, debug_user="mm_no_such_user"))
    assert TestClient(app).get("/ingredients").status_code == 401
