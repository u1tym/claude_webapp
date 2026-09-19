from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.config import load_config  # noqa: E402
from app.db import get_conn  # noqa: E402
from app.logger import LOG_FILE, close_logging, setup_logging  # noqa: E402


def _ensure_user(username: str) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM public.users WHERE username = %s", (username,))
            row = cur.fetchone()
            if row is not None:
                return int(row["id"])
            cur.execute(
                "INSERT INTO public.users (username, password_hash) VALUES (%s, 'x') RETURNING id",
                (username,),
            )
            row = cur.fetchone()
            assert row is not None
            return int(row["id"])


def _ensure_feature_assignment(user_id: int, feature_id: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.features (id, title, url, icon, icon_media_type)
                VALUES (%s, %s, %s, ''::bytea, 'image/png')
                ON CONFLICT (id) DO NOTHING
                """,
                (feature_id, feature_id, f"/portal_{feature_id.replace('-', '_')}/"),
            )
            cur.execute(
                """
                INSERT INTO public.menu_assignments (user_id, feature_id, display_order)
                VALUES (%s, %s, 1)
                ON CONFLICT DO NOTHING
                """,
                (user_id, feature_id),
            )


@pytest.fixture(autouse=True)
def log_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "log"
    setup_logging(log_dir=directory)
    yield directory
    close_logging()


def _log_text(log_dir: Path) -> str:
    return (log_dir / LOG_FILE).read_text(encoding="utf-8")


@pytest.fixture()
def allowed_username() -> str:
    return f"pm_test_{uuid.uuid4().hex[:12]}"


@pytest.fixture()
def other_username() -> str:
    return f"pm_test_other_{uuid.uuid4().hex[:12]}"


@pytest.fixture()
def unassigned_username() -> str:
    return f"pm_test_noaccess_{uuid.uuid4().hex[:12]}"


@pytest.fixture()
def allowed_user_id(allowed_username: str) -> int:
    user_id = _ensure_user(allowed_username)
    _ensure_feature_assignment(user_id, "password-management")
    return user_id


@pytest.fixture()
def other_user_id(other_username: str) -> int:
    user_id = _ensure_user(other_username)
    _ensure_feature_assignment(user_id, "password-management")
    return user_id


@pytest.fixture()
def unassigned_user_id(unassigned_username: str) -> int:
    return _ensure_user(unassigned_username)


def _client_as(monkeypatch: pytest.MonkeyPatch, username: str | None):
    from app.main import app
    from fastapi.testclient import TestClient

    cfg = load_config()
    patched = cfg.__class__(
        db_server=cfg.db_server,
        db_name=cfg.db_name,
        db_port=cfg.db_port,
        db_username=cfg.db_username,
        db_password=cfg.db_password,
        cors_origins=cfg.cors_origins,
        session_timeout_minutes=cfg.session_timeout_minutes,
        debug_user=username,
        log_max_bytes=cfg.log_max_bytes,
        log_backup_count=cfg.log_backup_count,
    )
    monkeypatch.setattr("app.deps.load_config", lambda: patched)
    return TestClient(app)


def test_settings_unauthenticated(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client_as(monkeypatch, None)
    res = client.get("/settings")
    assert res.status_code == 200
    body = res.json()
    assert body["login_url"].endswith("/login") or "login" in body["login_url"]
    assert "session_id" not in res.text


def test_passwords_require_login(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client_as(monkeypatch, None)
    res = client.get("/passwords")
    assert res.status_code == 401
    assert res.json() == {"detail": "未ログイン"}


def test_passwords_require_assignment(monkeypatch: pytest.MonkeyPatch, unassigned_user_id: int, unassigned_username: str) -> None:
    client = _client_as(monkeypatch, unassigned_username)
    res = client.get("/passwords")
    assert res.status_code == 403
    assert res.json() == {"detail": "権限がありません"}


def test_password_crud_search_and_isolation(
    monkeypatch: pytest.MonkeyPatch,
    allowed_user_id: int,
    allowed_username: str,
    other_user_id: int,
    other_username: str,
    log_dir: Path,
) -> None:
    client = _client_as(monkeypatch, allowed_username)

    created = client.post(
        "/passwords",
        json={
            "title": "Googleアカウント",
            "userword": "user@example.com",
            "psword": "MyP@ssword123",
            "site": "https://accounts.google.com",
            "memo": "メインアカウント",
        },
    )
    assert created.status_code == 201
    entry = created.json()
    assert entry["psword"] == "MyP@ssword123"

    # duplicate title for the same user fails
    dup = client.post(
        "/passwords",
        json={"title": "Googleアカウント", "userword": "x", "psword": "y"},
    )
    assert dup.status_code == 409

    # blank fields fail
    blank = client.post("/passwords", json={"title": "  ", "userword": "x", "psword": "y"})
    assert blank.status_code == 400

    # list excludes psword
    listed = client.get("/passwords")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert "psword" not in listed.json()["items"][0]

    # search matches on site/memo too
    found = client.get("/passwords", params={"keyword": "メイン"})
    assert found.json()["total"] == 1
    not_found = client.get("/passwords", params={"keyword": "該当なし"})
    assert not_found.json()["total"] == 0

    # single get includes psword
    fetched = client.get(f"/passwords/{entry['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["psword"] == "MyP@ssword123"

    # update: title can change, still scoped to same user
    updated = client.patch(
        f"/passwords/{entry['id']}",
        json={
            "title": "Googleアカウント（変更後）",
            "userword": "user@example.com",
            "psword": "NewP@ss456",
            "site": None,
            "memo": None,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Googleアカウント（変更後）"
    assert updated.json()["psword"] == "NewP@ss456"

    # another user cannot see or modify this entry
    other_client = _client_as(monkeypatch, other_username)
    other_get = other_client.get(f"/passwords/{entry['id']}")
    assert other_get.status_code == 404
    other_delete = other_client.delete(f"/passwords/{entry['id']}")
    assert other_delete.status_code == 404
    other_list = other_client.get("/passwords")
    assert other_list.json()["total"] == 0

    # delete then re-create with the same (updated) title succeeds
    deleted = client.delete(f"/passwords/{entry['id']}")
    assert deleted.status_code == 204
    missing = client.get(f"/passwords/{entry['id']}")
    assert missing.status_code == 404

    recreated = client.post(
        "/passwords",
        json={"title": "Googleアカウント（変更後）", "userword": "u", "psword": "p"},
    )
    assert recreated.status_code == 201

    text = _log_text(log_dir)
    assert "パスワードエントリ登録成功" in text
    assert "MyP@ssword123" not in text
    assert "NewP@ss456" not in text
