from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repos import insert_assignment, insert_feature, insert_user, logical_delete_user
from app.security import hash_password, to_data_url
from png_bytes import PNG_1X1


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def test_login_empty_is_400(client: TestClient) -> None:
    res = client.post("/auth/login", json={"username": "", "password": "x"})
    assert res.status_code == 400
    assert res.json() == {"detail": "入力が不正です"}


def test_login_failure_is_generic(client: TestClient) -> None:
    res = client.post("/auth/login", json={"username": "no-such-user", "password": "wrong"})
    assert res.status_code == 401
    assert res.json() == {"detail": "ログインできませんでした"}
    assert "session_id" not in res.text


def test_login_deleted_user_fails(client: TestClient) -> None:
    username = _unique("del")
    user = insert_user(username, hash_password("secret"))
    logical_delete_user(user.id)
    res = client.post("/auth/login", json={"username": username, "password": "secret"})
    assert res.status_code == 401
    assert res.json() == {"detail": "ログインできませんでした"}


def test_login_logout_session_and_menu(client: TestClient) -> None:
    username = _unique("ok")
    user = insert_user(username, hash_password("secret"))
    feature_id = _unique("feat")
    insert_feature(feature_id, "デモ", "http://example.local/demo", PNG_1X1, "image/png")
    insert_assignment(user.id, feature_id, 1)

    login = client.post("/auth/login", json={"username": username, "password": "secret"})
    assert login.status_code == 204
    assert "session_id" in login.cookies
    assert login.content == b""

    session = client.get("/auth/session")
    assert session.status_code == 200
    assert session.json() == {"username": username}
    assert "session_id" not in session.text

    menu = client.get("/menu")
    assert menu.status_code == 200
    items = menu.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == feature_id
    assert items[0]["title"] == "デモ"
    assert items[0]["url"] == "http://example.local/demo"
    assert items[0]["icon"] == to_data_url("image/png", PNG_1X1)

    other = _unique("other")
    other_user = insert_user(other, hash_password("secret"))
    other_feat = _unique("ofeat")
    insert_feature(other_feat, "他", "http://example.local/other", PNG_1X1, "image/png")
    insert_assignment(other_user.id, other_feat, 1)
    menu2 = client.get("/menu")
    ids = {item["id"] for item in menu2.json()["items"]}
    assert other_feat not in ids

    logout = client.post("/auth/logout")
    assert logout.status_code == 204
    again = client.get("/auth/session")
    assert again.status_code == 401
    assert again.json() == {"detail": "未ログイン"}


def test_menu_requires_login(client: TestClient) -> None:
    res = client.get("/menu")
    assert res.status_code == 401
    assert res.json() == {"detail": "未ログイン"}


def test_settings_has_data_urls(client: TestClient) -> None:
    res = client.get("/settings")
    assert res.status_code == 200
    body = res.json()
    assert body["login_url"].endswith("/login")
    assert body["menu_url"].endswith("/menu")
    assert body["icon_system"].startswith("data:image/png;base64,")
    assert body["icon_settings"].startswith("data:image/")
    assert body["icon_back"].startswith("data:image/")
    assert "session_id" not in res.text


def test_to_data_url_format() -> None:
    url = to_data_url("image/png", PNG_1X1)
    assert url.startswith("data:image/png;base64,")
