"""設定の読み込みと、DB の失敗の扱いのテスト（design.md 起動・モジュール構成）。"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import psycopg2
import pytest
from fastapi.testclient import TestClient

import app.config as config
from app import db
from app.config import BACKEND_DIR, load_config
from app.logger import LOG_FILE
from conftest import Owner


def _env(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "test.env"
    path.write_text(text, encoding="utf-8")
    return path


def test_db_variable_names_in_both_forms(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    template = _env(tmp_path, "DB_SERVER=h1\nDB_PORT=6000\nDB_DATABASE=d1\nDB_USERNAME=u1\nDB_PASSWORD=p1\n")
    monkeypatch.setattr(config, "ENV_PATH", template)
    cfg = load_config()
    assert (cfg.db_server, cfg.db_port, cfg.db_name, cfg.db_username, cfg.db_password) == ("h1", 6000, "d1", "u1", "p1")
    legacy = _env(tmp_path, "Server=h2\nPort=6001\nDatabase=d2\nUsername=u2\nPassword=p2\n")
    monkeypatch.setattr(config, "ENV_PATH", legacy)
    cfg = load_config()
    assert (cfg.db_server, cfg.db_port, cfg.db_name, cfg.db_username, cfg.db_password) == ("h2", 6001, "d2", "u2", "p2")


def test_defaults_and_other_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "ENV_PATH", _env(tmp_path, ""))
    cfg = load_config()
    assert (cfg.db_server, cfg.db_port, cfg.db_name, cfg.db_username) == ("localhost", 5432, "tstdb", "tstuser")
    assert cfg.debug_user is None and cfg.session_timeout_minutes == 30
    assert cfg.log_max_bytes == 10485760 and cfg.log_backup_count == 5 and cfg.cors_origins == []
    monkeypatch.setattr(
        config,
        "ENV_PATH",
        _env(tmp_path, "DEBUG_USER= dev \nSESSION_TIMEOUT_MINUTES=5\nLOG_MAX_BYTES=100\nLOG_BACKUP_COUNT=2\n"),
    )
    cfg = load_config()
    assert (cfg.debug_user, cfg.session_timeout_minutes, cfg.log_max_bytes, cfg.log_backup_count) == ("dev", 5, 100, 2)


def test_cors_origins_have_loopback_aliases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "ENV_PATH", _env(tmp_path, "CORS_ORIGINS=http://localhost:5186, https://example.com\n"))
    assert load_config().cors_origins == [
        "http://localhost:5186",
        "http://127.0.0.1:5186",
        "http://[::1]:5186",
        "https://example.com",
    ]


def test_actual_env_file_is_for_this_feature() -> None:
    cfg = load_config()
    assert "http://localhost:5186" in cfg.cors_origins
    assert cfg.db_name  # backend/.env を読めている


def test_env_file_can_be_switched_by_environment_variable(tmp_path: Path) -> None:
    other = _env(tmp_path, "DB_DATABASE=other_db\n")
    code = "from app.config import ENV_PATH, load_config; print(ENV_PATH); print(load_config().db_name)"
    out = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_DIR,
        env={"CONTRACT_MANAGEMENT_ENV_FILE": str(other), "PATH": "", "SYSTEMROOT": "C:\\Windows"},
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert out == [str(other), "other_db"]


def test_log_file_name_and_rotation(tmp_path: Path) -> None:
    from app.logger import close_logging, setup_logging, write

    path = setup_logging(log_dir=tmp_path / "rot", max_bytes=300, backup_count=2)
    assert path.name == LOG_FILE == "contract-management.log"
    for i in range(40):
        write("INF", f"ローテーション確認 {i} " + "あ" * 20)
    close_logging()
    files = sorted(p.name for p in (tmp_path / "rot").iterdir())
    assert LOG_FILE in files and f"{LOG_FILE}.1" in files and f"{LOG_FILE}.2" in files
    assert f"{LOG_FILE}.3" not in files  # 世代数を超えたものは消える


def test_connection_failures_do_not_exhaust_the_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse() -> None:
        raise psycopg2.OperationalError("connection refused")

    with monkeypatch.context() as m:
        m.setattr(db, "_get_pool", refuse)
        for _ in range(db.POOL_MAX + 5):
            with pytest.raises(psycopg2.OperationalError):
                with db.get_conn():
                    pass
    # 失敗が続いたあとでも、接続できる（借りた枠が戻っている）
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS one")
            assert cur.fetchone()["one"] == 1


def test_db_failure_returns_500_and_logs_the_cause(
    make_owner: Callable[..., Owner], monkeypatch: pytest.MonkeyPatch, log_dir: Path
) -> None:
    from app.main import app

    owner = make_owner()
    c = TestClient(app, raise_server_exceptions=False)
    c.cookies.set("session_id", owner.session_id)

    def fail(*_a: object, **_k: object) -> None:
        raise psycopg2.OperationalError("could not connect to server: refused\nsecond line with detail")

    monkeypatch.setattr("app.services.category_service.repos.list_categories", fail)
    res = c.get("/categories")
    assert res.status_code == 500 and res.json() == {"detail": "サーバエラーです"}
    text = (log_dir / LOG_FILE).read_text(encoding="utf-8")
    assert "ERR" in text and "type=OperationalError" in text and "could not connect to server: refused" in text
    assert "second line" not in text
