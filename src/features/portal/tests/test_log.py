from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.logger import LOG_FILE, LOG_NAME, close_logging, setup_logging
from app.main import app
from app.repos import insert_assignment, insert_feature, insert_user, logical_delete_user
from app.security import hash_password
from png_bytes import PNG_1X1

_STAMP = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ")


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _log_text(log_dir: Path) -> str:
    return (log_dir / LOG_FILE).read_text(encoding="utf-8")


def test_load_config_log_rotation(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import config as config_mod

    monkeypatch.setattr(
        config_mod,
        "dotenv_values",
        lambda _path: {
            "CORS_ORIGINS": "http://localhost:5173",
            "LOG_MAX_BYTES": "2048",
            "LOG_BACKUP_COUNT": "3",
        },
    )
    cfg = config_mod.load_config()
    assert cfg.log_max_bytes == 2048
    assert cfg.log_backup_count == 3


def test_setup_logging_uses_rotation_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import config as config_mod

    monkeypatch.setattr(
        config_mod,
        "dotenv_values",
        lambda _path: {
            "CORS_ORIGINS": "http://localhost:5173",
            "LOG_MAX_BYTES": "4096",
            "LOG_BACKUP_COUNT": "7",
        },
    )
    close_logging()
    setup_logging(log_dir=tmp_path)
    handlers = logging.getLogger(LOG_NAME).handlers
    assert len(handlers) == 1
    handler = handlers[0]
    assert isinstance(handler, RotatingFileHandler)
    assert handler.maxBytes == 4096
    assert handler.backupCount == 7


def test_login_success_logs_input_and_result(
    client: TestClient,
    log_dir: Path,
) -> None:
    username = _unique("ok")
    password = "secret-pass"
    insert_user(username, hash_password(password))
    res = client.post("/auth/login", json={"username": username, "password": password})
    assert res.status_code == 204
    text = _log_text(log_dir)
    lines = [line for line in text.splitlines() if username in line]
    assert any(" INF ログイン要求 username=" + username in line for line in lines)
    assert any(" INF ログイン成功 username=" + username in line for line in lines)
    for line in lines:
        assert _STAMP.match(line)
    assert password not in text
    session_id = res.cookies.get("session_id")
    assert session_id
    assert session_id not in text
    assert "session_id=" not in text


def test_login_unknown_user_logs_internal_reason(
    client: TestClient,
    log_dir: Path,
) -> None:
    username = _unique("none")
    password = "wrong-pass"
    res = client.post("/auth/login", json={"username": username, "password": password})
    assert res.status_code == 401
    assert res.json() == {"detail": "ログインできませんでした"}
    text = _log_text(log_dir)
    assert f"INF ログイン要求 username={username}" in text
    assert f"WRN ログイン失敗 username={username} 理由=ユーザなし" in text
    assert "ユーザなし" not in res.text
    assert password not in text


def test_login_deleted_user_logs_internal_reason(
    client: TestClient,
    log_dir: Path,
) -> None:
    username = _unique("del")
    password = "secret-pass"
    user = insert_user(username, hash_password(password))
    logical_delete_user(user.id)
    res = client.post("/auth/login", json={"username": username, "password": password})
    assert res.status_code == 401
    assert res.json() == {"detail": "ログインできませんでした"}
    text = _log_text(log_dir)
    assert f"WRN ログイン失敗 username={username} 理由=論理削除" in text
    assert "論理削除" not in res.text
    assert password not in text


def test_login_bad_password_logs_internal_reason(
    client: TestClient,
    log_dir: Path,
) -> None:
    username = _unique("bad")
    insert_user(username, hash_password("correct-pass"))
    password = "wrong-pass"
    res = client.post("/auth/login", json={"username": username, "password": password})
    assert res.status_code == 401
    assert res.json() == {"detail": "ログインできませんでした"}
    text = _log_text(log_dir)
    assert f"WRN ログイン失敗 username={username} 理由=パスワード不一致" in text
    assert "パスワード不一致" not in res.text
    assert password not in text


def test_login_blank_logs_invalid_input(
    client: TestClient,
    log_dir: Path,
) -> None:
    res = client.post("/auth/login", json={"username": "", "password": "x"})
    assert res.status_code == 400
    assert res.json() == {"detail": "入力が不正です"}
    text = _log_text(log_dir)
    assert "INF ログイン要求 username=" in text
    assert "WRN ログイン失敗 username= 理由=入力不正" in text


def test_menu_get_logs_urls_from_db(
    client: TestClient,
    log_dir: Path,
) -> None:
    username = _unique("menu")
    user = insert_user(username, hash_password("secret"))
    feature_id = _unique("feat")
    insert_feature(feature_id, "デモ", "http://example.local/demo", PNG_1X1, "image/png")
    insert_assignment(user.id, feature_id, 1)
    login = client.post("/auth/login", json={"username": username, "password": "secret"})
    assert login.status_code == 204

    res = client.get("/menu")
    assert res.status_code == 200
    text = _log_text(log_dir)
    assert f"INF メニュー取得要求 username={username}" in text
    assert f"INF メニュー取得成功 username={username} count=1" in text
    assert f"INF メニュー項目 id={feature_id} title=デモ url=http://example.local/demo" in text
    session_id = login.cookies.get("session_id")
    assert session_id
    assert session_id not in text


def test_menu_nav_log_writes_from_db_and_destination(
    client: TestClient,
    log_dir: Path,
) -> None:
    username = _unique("nav")
    insert_user(username, hash_password("secret"))
    login = client.post("/auth/login", json={"username": username, "password": "secret"})
    assert login.status_code == 204

    res = client.post(
        "/menu/nav-log",
        json={
            "id": "schedule",
            "title": "予定",
            "from_db": "https://example.local/portal_schedule",
            "destination": "https://example.local/portal_schedule?a=123",
            "error": "",
        },
    )
    assert res.status_code == 204
    text = _log_text(log_dir)
    assert (
        f"INF メニュー遷移 username={username} id=schedule title=予定"
        " from_db=https://example.local/portal_schedule"
        " destination=https://example.local/portal_schedule?a=123 error="
    ) in text
    session_id = login.cookies.get("session_id")
    assert session_id
    assert session_id not in text
    assert "session_id=" not in text
