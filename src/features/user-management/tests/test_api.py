from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import FEATURE_ID, load_config
from app.logger import LOG_FILE
from app.main import app
from app.repos import (
    assignment_exists,
    get_feature,
    insert_assignment,
    insert_feature,
    insert_session,
    insert_user,
    logical_delete_user,
)
from app.security import hash_password, session_expiry, to_data_url
from png_bytes import PNG_1X1


def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


def _ensure_feature() -> None:
    if get_feature(FEATURE_ID) is None:
        insert_feature(
            FEATURE_ID,
            "ユーザ管理",
            "http://localhost:5174/users",
            PNG_1X1,
            "image/png",
        )


def _operator() -> tuple[int, str]:
    _ensure_feature()
    username = _unique("op")
    user = insert_user(username, hash_password("secret"))
    if not assignment_exists(user.id, FEATURE_ID):
        insert_assignment(user.id, FEATURE_ID, 1)
    return user.id, username


def _client_as(user_id: int) -> TestClient:
    from uuid import uuid4 as new_id

    client = TestClient(app)
    cfg = load_config()
    session_id = new_id()
    insert_session(session_id, user_id, session_expiry(cfg.session_timeout_minutes))
    client.cookies.set("session_id", str(session_id))
    return client


def _log_text(log_dir: Path) -> str:
    return (log_dir / LOG_FILE).read_text(encoding="utf-8")


def test_settings_unauthenticated() -> None:
    client = TestClient(app)
    res = client.get("/settings")
    assert res.status_code == 200
    body = res.json()
    assert body["login_url"].endswith("/login")
    assert body["menu_url"].endswith("/menu")
    assert body["icon_system"].startswith("data:image/")
    assert body["icon_back"].startswith("data:image/")
    assert "session_id" not in res.text


def test_users_require_login() -> None:
    client = TestClient(app)
    res = client.get("/users")
    assert res.status_code == 401
    assert res.json() == {"detail": "未ログイン"}


def test_users_require_assignment() -> None:
    username = _unique("noas")
    user = insert_user(username, hash_password("secret"))
    client = _client_as(user.id)
    res = client.get("/users")
    assert res.status_code == 403
    assert res.json() == {"detail": "権限がありません"}


def test_user_crud_and_self_delete(log_dir: Path) -> None:
    op_id, _op_name = _operator()
    client = _client_as(op_id)
    listed = client.get("/users")
    assert listed.status_code == 200
    for item in listed.json()["items"]:
        assert "password" not in item
        assert "email" in item
        if item["id"] == op_id:
            assert item["is_self"] is True

    created = client.post(
        "/users",
        json={"username": _unique("new"), "password": "pw-secret", "email": "new@example.com"},
    )
    assert created.status_code == 201
    new_id = created.json()["id"]
    assert created.json()["is_self"] is False
    assert created.json()["email"] == "new@example.com"
    assert "password" not in created.json()

    dup = client.post(
        "/users",
        json={"username": created.json()["username"], "password": "x", "email": "dup@example.com"},
    )
    assert dup.status_code == 409
    assert dup.json() == {"detail": "保存できませんでした"}

    renamed = _unique("ren")
    patched = client.patch(
        f"/users/{new_id}",
        json={"username": renamed, "email": "ren@example.com"},
    )
    assert patched.status_code == 200
    assert patched.json()["username"] == renamed
    assert patched.json()["email"] == "ren@example.com"

    deleted = client.delete(f"/users/{new_id}")
    assert deleted.status_code == 204
    again = client.delete(f"/users/{new_id}")
    assert again.status_code == 404

    self_del = client.delete(f"/users/{op_id}")
    assert self_del.status_code == 409
    assert self_del.json() == {"detail": "削除できませんでした"}

    text = _log_text(log_dir)
    assert "ユーザ追加要求" in text
    assert "ユーザ追加成功" in text
    assert "pw-secret" not in text
    assert "自己削除" in text


def test_deleted_user_not_listed() -> None:
    op_id, _ = _operator()
    gone = insert_user(_unique("gone"), hash_password("x"))
    logical_delete_user(gone.id)
    client = _client_as(op_id)
    ids = {item["id"] for item in client.get("/users").json()["items"]}
    assert gone.id not in ids


def test_feature_crud_and_protected(log_dir: Path) -> None:
    op_id, _ = _operator()
    client = _client_as(op_id)
    icon = to_data_url("image/png", PNG_1X1)
    feature_id = _unique("feat")
    created = client.post(
        "/features",
        json={"id": feature_id, "title": "デモ", "url": "http://localhost/x", "icon": icon},
    )
    assert created.status_code == 201
    assert created.json()["icon"].startswith("data:image/png;base64,")
    assert created.json()["is_protected"] is False

    dup = client.post(
        "/features",
        json={"id": feature_id, "title": "デモ", "url": "http://localhost/x", "icon": icon},
    )
    assert dup.status_code == 409

    patched = client.patch(
        f"/features/{feature_id}",
        json={"title": "変更", "url": "http://localhost/y"},
    )
    assert patched.status_code == 200
    assert patched.json()["id"] == feature_id
    assert patched.json()["title"] == "変更"

    listed = client.get("/features")
    ids = {item["id"] for item in listed.json()["items"]}
    assert feature_id in ids
    protected = [item for item in listed.json()["items"] if item["id"] == FEATURE_ID]
    assert protected
    assert protected[0]["is_protected"] is True

    banned = client.delete(f"/features/{FEATURE_ID}")
    assert banned.status_code == 409
    assert banned.json() == {"detail": "削除できませんでした"}

    removed = client.delete(f"/features/{feature_id}")
    assert removed.status_code == 204
    missing = client.delete(f"/features/{feature_id}")
    assert missing.status_code == 404

    text = _log_text(log_dir)
    assert "機能追加成功" in text
    assert "本機能" in text


def test_assignment_crud_and_self_unassign() -> None:
    op_id, _ = _operator()
    client = _client_as(op_id)
    other = insert_user(_unique("asg"), hash_password("x"))
    feature_id = _unique("af")
    insert_feature(feature_id, "割当先", "http://localhost/a", PNG_1X1, "image/png")

    created = client.post(
        "/assignments",
        json={"user_id": other.id, "feature_id": feature_id, "display_order": 2},
    )
    assert created.status_code == 201
    assert created.json()["can_unassign"] is True

    dup = client.post(
        "/assignments",
        json={"user_id": other.id, "feature_id": feature_id, "display_order": 3},
    )
    assert dup.status_code == 409

    listed = client.get("/assignments")
    assert listed.status_code == 200
    self_rows = [
        item
        for item in listed.json()["items"]
        if item["user_id"] == op_id and item["feature_id"] == FEATURE_ID
    ]
    assert self_rows
    assert self_rows[0]["can_unassign"] is False

    banned = client.delete(f"/assignments/{op_id}/{FEATURE_ID}")
    assert banned.status_code == 409
    assert banned.json() == {"detail": "削除できませんでした"}

    removed = client.delete(f"/assignments/{other.id}/{feature_id}")
    assert removed.status_code == 204
    missing = client.delete(f"/assignments/{other.id}/{feature_id}")
    assert missing.status_code == 404
