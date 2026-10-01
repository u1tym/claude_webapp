from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app import deps
from app.config import load_config
from app.deps import AuthContext, get_current_user
from app.logger import LOG_FILE
from app.main import app as room_app
from helpers import (
    assign_feature,
    ensure_feature,
    get_api_key_last_used,
    get_session_expiry,
    insert_api_key,
    insert_session,
    insert_user,
    set_session_expiry,
    unique,
)


def _protected_app() -> FastAPI:
    """認証の判定だけを確かめるための、保護された 1 本のルートを持つアプリ。"""
    app = FastAPI()

    @app.get("/protected")
    def protected(auth: AuthContext = Depends(get_current_user)) -> dict[str, str]:
        return {"username": auth.user.username}

    return app


def _log_text(log_dir: Path) -> str:
    return (log_dir / LOG_FILE).read_text(encoding="utf-8")


def _assigned_user() -> int:
    ensure_feature()
    user_id = insert_user(unique("room_op"))
    assign_feature(user_id)
    return user_id


def _cookie_client(user_id: int) -> tuple[TestClient, "object"]:
    client = TestClient(_protected_app())
    session_id = insert_session(user_id, load_config().session_timeout_minutes)
    client.cookies.set("session_id", str(session_id))
    return client, session_id


# ---- GET /settings（認証不要） ----


def test_settingsは認証なしで返る() -> None:
    res = TestClient(room_app).get("/settings")
    assert res.status_code == 200
    body = res.json()
    assert body["login_url"]
    assert body["menu_url"]
    assert body["icon_system"].startswith("data:image/")
    assert body["icon_back"].startswith("data:image/")
    assert "session_id" not in res.text


def test_settingsはAuthorizationヘッダがあっても判定しない() -> None:
    res = TestClient(room_app).get("/settings", headers={"Authorization": "Bearer invalid"})
    assert res.status_code == 200


# ---- Cookie ----


def test_Cookieなしは未ログイン(log_dir: Path) -> None:
    res = TestClient(_protected_app()).get("/protected")
    assert res.status_code == 401
    assert res.json() == {"detail": "未ログイン"}
    assert "認証失敗" in _log_text(log_dir)


def test_Cookieの値が不正なら未ログイン() -> None:
    client = TestClient(_protected_app())
    client.cookies.set("session_id", "not-a-uuid")
    assert client.get("/protected").status_code == 401


def test_存在しないセッションは未ログイン() -> None:
    client = TestClient(_protected_app())
    client.cookies.set("session_id", "00000000-0000-0000-0000-000000000000")
    assert client.get("/protected").status_code == 401


def test_割当ありのCookieは許可され期限が延びる() -> None:
    user_id = _assigned_user()
    client, session_id = _cookie_client(user_id)
    soon = datetime.now(timezone.utc) + timedelta(minutes=1)
    set_session_expiry(session_id, soon)  # type: ignore[arg-type]

    res = client.get("/protected")

    assert res.status_code == 200
    assert get_session_expiry(session_id) > soon + timedelta(minutes=10)  # type: ignore[arg-type]


def test_期限切れのセッションは未ログイン() -> None:
    user_id = _assigned_user()
    client, session_id = _cookie_client(user_id)
    set_session_expiry(session_id, datetime.now(timezone.utc) - timedelta(seconds=1))  # type: ignore[arg-type]
    assert client.get("/protected").status_code == 401


def test_論理削除済みユーザのセッションは未ログイン() -> None:
    ensure_feature()
    user_id = insert_user(unique("room_del"), is_deleted=True)
    assign_feature(user_id)
    client, _ = _cookie_client(user_id)
    assert client.get("/protected").status_code == 401


def test_割当なしは権限なし(log_dir: Path) -> None:
    ensure_feature()
    user_id = insert_user(unique("room_noas"))
    client, _ = _cookie_client(user_id)
    res = client.get("/protected")
    assert res.status_code == 403
    assert res.json() == {"detail": "権限がありません"}
    assert "認可失敗" in _log_text(log_dir)


# ---- DEBUG_USER ----


def _with_debug_user(monkeypatch: pytest.MonkeyPatch, username: str) -> None:
    cfg = dataclasses.replace(load_config(), debug_user=username)
    monkeypatch.setattr(deps, "load_config", lambda: cfg)


def test_DEBUG_USERはCookieなしでそのユーザとして処理する(monkeypatch: pytest.MonkeyPatch) -> None:
    ensure_feature()
    name = unique("room_dbg")
    assign_feature(insert_user(name))
    _with_debug_user(monkeypatch, name)
    res = TestClient(_protected_app()).get("/protected")
    assert res.status_code == 200
    assert res.json() == {"username": name}


def test_DEBUG_USERでも割当を判定する(monkeypatch: pytest.MonkeyPatch) -> None:
    ensure_feature()
    name = unique("room_dbg_noas")
    insert_user(name)
    _with_debug_user(monkeypatch, name)
    assert TestClient(_protected_app()).get("/protected").status_code == 403


def test_DEBUG_USERが存在しないユーザなら未ログイン(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_debug_user(monkeypatch, unique("room_nobody"))
    assert TestClient(_protected_app()).get("/protected").status_code == 401


# ---- API キー ----


def _key() -> str:
    return "rk_" + unique("k") + "_secretsecretsecret"


def test_APIキーで許可され最終利用日時が更新されセッションは作られない(log_dir: Path) -> None:
    user_id = _assigned_user()
    key = _key()
    key_id = insert_api_key(user_id, key)
    assert get_api_key_last_used(key_id) is None

    res = TestClient(_protected_app()).get("/protected", headers={"Authorization": f"Bearer {key}"})

    assert res.status_code == 200
    assert get_api_key_last_used(key_id) is not None
    assert "set-cookie" not in res.headers
    log = _log_text(log_dir)
    assert "API キー認証成功" in log
    assert key[:12] in log


def test_スキーム名の大文字小文字は区別しない() -> None:
    user_id = _assigned_user()
    key = _key()
    insert_api_key(user_id, key)
    res = TestClient(_protected_app()).get("/protected", headers={"Authorization": f"bEaReR {key}"})
    assert res.status_code == 200


@pytest.mark.parametrize("header", ["Basic abc", "Bearer", "Bearer   ", "abc"])
def test_Bearer方式でない_空のキーは未ログイン(header: str) -> None:
    res = TestClient(_protected_app()).get("/protected", headers={"Authorization": header})
    assert res.status_code == 401
    assert res.headers["www-authenticate"] == "Bearer"
    assert res.json() == {"detail": "未ログイン"}


def test_該当なしのキーは未ログイン() -> None:
    res = TestClient(_protected_app()).get("/protected", headers={"Authorization": f"Bearer {_key()}"})
    assert res.status_code == 401
    assert res.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "kwargs, reason",
    [({"revoked": True}, "失効済み"), ({"expired": True}, "期限切れ")],
)
def test_失効_期限切れのキーは未ログインで最終利用日時を更新しない(
    kwargs: dict[str, bool], reason: str, log_dir: Path
) -> None:
    user_id = _assigned_user()
    key = _key()
    key_id = insert_api_key(user_id, key, **kwargs)
    res = TestClient(_protected_app()).get("/protected", headers={"Authorization": f"Bearer {key}"})
    assert res.status_code == 401
    assert get_api_key_last_used(key_id) is None
    assert reason in _log_text(log_dir)


def test_持ち主が論理削除済みのキーは未ログイン() -> None:
    ensure_feature()
    user_id = insert_user(unique("room_keydel"), is_deleted=True)
    assign_feature(user_id)
    key = _key()
    insert_api_key(user_id, key)
    res = TestClient(_protected_app()).get("/protected", headers={"Authorization": f"Bearer {key}"})
    assert res.status_code == 401


def test_持ち主に割当がないキーは権限なし() -> None:
    ensure_feature()
    user_id = insert_user(unique("room_keynoas"))
    key = _key()
    key_id = insert_api_key(user_id, key)
    res = TestClient(_protected_app()).get("/protected", headers={"Authorization": f"Bearer {key}"})
    assert res.status_code == 403
    assert get_api_key_last_used(key_id) is None


def test_APIキーが失敗してもCookieには戻らない() -> None:
    user_id = _assigned_user()
    client, _ = _cookie_client(user_id)
    assert client.get("/protected").status_code == 200  # Cookie だけなら許可される
    res = client.get("/protected", headers={"Authorization": f"Bearer {_key()}"})
    assert res.status_code == 401


def test_APIキー全体とハッシュはログに出ない(log_dir: Path) -> None:
    from app.security import hash_api_key

    key = _key()
    TestClient(_protected_app()).get("/protected", headers={"Authorization": f"Bearer {key}"})
    log = _log_text(log_dir)
    assert key not in log
    assert hash_api_key(key) not in log
    assert key[:12] in log
