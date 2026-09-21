from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.config as config
from app.main import app

from conftest import log_text


def _load(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, text: str) -> config.Config:
    env = tmp_path / ".env"
    env.write_text(text, encoding="utf-8")
    monkeypatch.setattr(config, "ENV_PATH", env)
    return config.load_config()


def test_template_names(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg = _load(monkeypatch, tmp_path, "DB_SERVER=h1\nDB_PORT=6543\nDB_DATABASE=d1\nDB_USERNAME=u1\nDB_PASSWORD=p1\n")
    assert (cfg.db_server, cfg.db_port, cfg.db_name, cfg.db_username, cfg.db_password) == ("h1", 6543, "d1", "u1", "p1")


def test_names_used_by_other_features(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """他機能の .env（Server / Database / Port / Username / Password）をそのまま使っても読める。"""
    cfg = _load(monkeypatch, tmp_path, "Server=h2\nPort=6544\nDatabase=d2\nUsername=u2\nPassword=p2\n")
    assert (cfg.db_server, cfg.db_port, cfg.db_name, cfg.db_username, cfg.db_password) == ("h2", 6544, "d2", "u2", "p2")


def test_template_names_win_when_both_are_given(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg = _load(monkeypatch, tmp_path, "DB_SERVER=new\nServer=old\n")
    assert cfg.db_server == "new"


def test_db_failure_logs_cause_without_password(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, log_dir: Path
) -> None:
    """DB に接続できないとき、画面には内部理由を出さず、ログには原因（先頭の 1 行）を残す。パスワードは出さない。"""
    env = tmp_path / ".env"
    env.write_text("DB_SERVER=127.0.0.1\nDB_PORT=1\nDB_DATABASE=nope\nDB_USERNAME=someone\nDB_PASSWORD=secret-pw-xyz\n", encoding="utf-8")
    monkeypatch.setattr(config, "ENV_PATH", env)
    monkeypatch.setattr("app.db._pool", None)  # 新しい設定でプールを作り直す
    res = TestClient(app, raise_server_exceptions=False).get("/settings")
    assert res.status_code == 500
    assert res.json() == {"detail": "サーバエラーです"}
    text = log_text(log_dir)
    assert "OperationalError" in text and "内容=" in text
    assert "secret-pw-xyz" not in text


def test_repeated_db_failures_do_not_exhaust_connection_slots(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """DB に接続できない状態が続いても、枠（同時接続の上限）を使い切らず、毎回すぐ失敗を返す。"""
    from app.db import POOL_MAX

    env = tmp_path / ".env"
    env.write_text("DB_SERVER=127.0.0.1\nDB_PORT=1\nDB_DATABASE=nope\nDB_USERNAME=u\nDB_PASSWORD=p\n", encoding="utf-8")
    monkeypatch.setattr(config, "ENV_PATH", env)
    monkeypatch.setattr("app.db._pool", None)
    client = TestClient(app, raise_server_exceptions=False)
    for _ in range(POOL_MAX + 5):
        assert client.get("/settings").status_code == 500
