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
    return f"km_test_{uuid.uuid4().hex[:12]}"


@pytest.fixture()
def unassigned_username() -> str:
    return f"km_test_noaccess_{uuid.uuid4().hex[:12]}"


@pytest.fixture()
def allowed_user_id(allowed_username: str) -> int:
    user_id = _ensure_user(allowed_username)
    _ensure_feature_assignment(user_id, "knowhow-management")
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
    assert "session_id" not in res.text


def test_major_categories_require_login(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client_as(monkeypatch, None)
    res = client.get("/major-categories")
    assert res.status_code == 401
    assert res.json() == {"detail": "未ログイン"}


def test_major_categories_require_assignment(
    monkeypatch: pytest.MonkeyPatch, unassigned_user_id: int, unassigned_username: str
) -> None:
    client = _client_as(monkeypatch, unassigned_username)
    res = client.get("/major-categories")
    assert res.status_code == 403
    assert res.json() == {"detail": "権限がありません"}


def test_full_hierarchy_crud_search_reorder_and_cascade_delete(
    monkeypatch: pytest.MonkeyPatch,
    allowed_user_id: int,
    allowed_username: str,
    log_dir: Path,
) -> None:
    client = _client_as(monkeypatch, allowed_username)

    major = client.post("/major-categories", json={"name": "サーバ運用"})
    assert major.status_code == 201
    major_id = major.json()["id"]

    dup_major = client.post("/major-categories", json={"name": "サーバ運用"})
    assert dup_major.status_code == 409

    renamed_major = client.patch(f"/major-categories/{major_id}", json={"name": "サーバ運用A"})
    assert renamed_major.status_code == 200
    assert renamed_major.json()["name"] == "サーバ運用A"

    middle = client.post(f"/major-categories/{major_id}/middle-categories", json={"name": "バックアップ"})
    assert middle.status_code == 201
    middle_id = middle.json()["id"]

    dup_middle = client.post(f"/major-categories/{major_id}/middle-categories", json={"name": "バックアップ"})
    assert dup_middle.status_code == 409

    kh1 = client.post(
        "/knowhows",
        json={"title": "設定手順1", "keywords": "初期設定", "content": "1. abc", "middle_category_id": middle_id},
    )
    assert kh1.status_code == 201
    kh1_id = kh1.json()["id"]

    kh2 = client.post(
        "/knowhows",
        json={"title": "設定手順2", "keywords": None, "content": "2. def", "middle_category_id": middle_id},
    )
    assert kh2.status_code == 201
    kh2_id = kh2.json()["id"]
    assert kh2.json()["display_order"] == kh1.json()["display_order"] + 1

    listed = client.get(f"/middle-categories/{middle_id}/knowhows")
    assert listed.status_code == 200
    assert [i["title"] for i in listed.json()["items"]] == ["設定手順1", "設定手順2"]
    assert "content" not in listed.json()["items"][0]

    swapped = client.post("/knowhows/swap-display-order", json={"knowhow_id_a": kh1_id, "knowhow_id_b": kh2_id})
    assert swapped.status_code == 204
    listed_after_swap = client.get(f"/middle-categories/{middle_id}/knowhows")
    assert [i["title"] for i in listed_after_swap.json()["items"]] == ["設定手順2", "設定手順1"]

    unclassified = client.post(
        "/knowhows",
        json={"title": "未分類ノウハウ", "content": "本文", "middle_category_id": None},
    )
    assert unclassified.status_code == 201
    assert unclassified.json()["middle_category_id"] is None

    found = client.get("/knowhows/search", params={"keyword": ["設定", "abc"]})
    assert found.status_code == 200
    titles = [i["title"] for i in found.json()["items"]]
    assert titles == ["設定手順1"]
    assert found.json()["items"][0]["major_category_name"] == "サーバ運用A"
    assert found.json()["items"][0]["middle_category_name"] == "バックアップ"

    not_found = client.get("/knowhows/search", params={"keyword": ["該当なし"]})
    assert not_found.json()["items"] == []

    detail = client.get(f"/knowhows/{kh1_id}")
    assert detail.status_code == 200
    assert detail.json()["content"] == "1. abc"

    # deleting the major category cascades to the middle category and its knowhows
    deleted_major = client.delete(f"/major-categories/{major_id}")
    assert deleted_major.status_code == 204
    assert client.get(f"/major-categories/{major_id}/middle-categories").status_code == 404
    assert client.get(f"/middle-categories/{middle_id}/knowhows").status_code == 404
    assert client.get(f"/knowhows/{kh1_id}").status_code == 404
    assert client.get(f"/knowhows/{kh2_id}").status_code == 404

    # the unclassified knowhow is untouched by the cascade
    assert client.get(f"/knowhows/{unclassified.json()['id']}").status_code == 200

    # re-creating a major category with the previously deleted name succeeds
    recreated = client.post("/major-categories", json={"name": "サーバ運用A"})
    assert recreated.status_code == 201

    text = _log_text(log_dir)
    assert "大項目削除成功" in text
    assert "1. abc" not in text
