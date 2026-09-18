from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import load_config
from app.logger import LOG_FILE
from app.main import app
from helpers import assign_feature, ensure_feature, insert_session, insert_user, unique


def _log_text(log_dir: Path) -> str:
    return (log_dir / LOG_FILE).read_text(encoding="utf-8")


def _operator() -> TestClient:
    ensure_feature()
    user_id = insert_user(unique("op"))
    assign_feature(user_id)
    client = TestClient(app)
    cfg = load_config()
    session_id = insert_session(user_id, cfg.session_timeout_minutes)
    client.cookies.set("session_id", str(session_id))
    return client


def test_settings_unauthenticated() -> None:
    client = TestClient(app)
    res = client.get("/settings")
    assert res.status_code == 200
    body = res.json()
    assert "login_url" in body
    assert "menu_url" in body
    assert body["icon_system"].startswith("data:image/")
    assert body["icon_back"].startswith("data:image/")
    assert "session_id" not in res.text


def test_status_requires_login() -> None:
    client = TestClient(app)
    res = client.get("/status")
    assert res.status_code == 401
    assert res.json() == {"detail": "未ログイン"}


def test_start_requires_login() -> None:
    client = TestClient(app)
    res = client.post("/start", json={"confirmed": False})
    assert res.status_code == 401
    assert res.json() == {"detail": "未ログイン"}


def test_status_requires_assignment() -> None:
    ensure_feature()
    user_id = insert_user(unique("noas"))
    client = TestClient(app)
    cfg = load_config()
    session_id = insert_session(user_id, cfg.session_timeout_minutes)
    client.cookies.set("session_id", str(session_id))
    res = client.get("/status")
    assert res.status_code == 403
    assert res.json() == {"detail": "権限がありません"}


def test_status_is_up_true(monkeypatch: pytest.MonkeyPatch, log_dir: Path) -> None:
    monkeypatch.setattr("app.services.status_service.run_ping", lambda _host, _timeout: (True, "応答あり"))
    client = _operator()
    res = client.get("/status")
    assert res.status_code == 200
    assert res.json() == {"is_up": True}
    text = _log_text(log_dir)
    assert "状態参照要求 username=" in text
    assert "is_up=true" in text
    assert "session_id=" not in text


def test_status_is_up_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.status_service.run_ping",
        lambda _host, _timeout: (False, "応答なし code=1"),
    )
    client = _operator()
    res = client.get("/status")
    assert res.status_code == 200
    assert res.json() == {"is_up": False}


def test_start_missing_confirmed() -> None:
    client = _operator()
    res = client.post("/start", json={})
    assert res.status_code == 400
    assert res.json() == {"detail": "入力が不正です"}


def test_start_success(monkeypatch: pytest.MonkeyPatch, log_dir: Path) -> None:
    monkeypatch.setattr("app.services.start_service.execute_wol", lambda _mac: 0)
    client = _operator()
    res = client.post("/start", json={"confirmed": False})
    assert res.status_code == 204
    assert res.content == b""
    text = _log_text(log_dir)
    assert "起動指示 username=" in text
    assert "confirmed=false" in text
    assert "起動処理成功" in text
    assert "session_id=" not in text


def test_start_failure_is_409(monkeypatch: pytest.MonkeyPatch, log_dir: Path) -> None:
    monkeypatch.setattr("app.services.start_service.execute_wol", lambda _mac: 1)
    client = _operator()
    res = client.post("/start", json={"confirmed": True})
    assert res.status_code == 409
    assert res.json() == {"detail": "実行できませんでした"}
    text = _log_text(log_dir)
    assert "終了コード=1" in text
    assert "終了コード=1" not in res.text


def test_start_busy_is_409(monkeypatch: pytest.MonkeyPatch) -> None:
    def slow(_mac: str) -> int:
        time.sleep(0.4)
        return 0

    monkeypatch.setattr("app.services.start_service.execute_wol", slow)
    client = _operator()
    results: list[int] = []

    def call() -> None:
        results.append(client.post("/start", json={"confirmed": False}).status_code)

    first = threading.Thread(target=call)
    second = threading.Thread(target=call)
    first.start()
    time.sleep(0.05)
    second.start()
    first.join()
    second.join()
    assert sorted(results) == [204, 409]
