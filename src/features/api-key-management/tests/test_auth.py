from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from conftest import AppUser, login, set_user_deleted


def test_settings_without_login(client: TestClient) -> None:
    res = client.get("/settings")
    assert res.status_code == 200
    body = res.json()
    assert set(body) == {"login_url", "menu_url", "icon_system", "icon_back"}


def test_unauthenticated_is_401(client: TestClient) -> None:
    for method, path in [("get", "/api-keys"), ("post", "/api-keys"), ("post", "/api-keys/1/revoke")]:
        res = getattr(client, method)(path, json={"name": "x"}) if method == "post" else client.get(path)
        assert res.status_code == 401
        assert res.json() == {"detail": "未ログイン"}


def test_unassigned_is_403(client: TestClient, make_user: Callable[..., AppUser]) -> None:
    user = make_user(assigned=False)
    res = login(client, user).get("/api-keys")
    assert res.status_code == 403
    assert res.json() == {"detail": "権限がありません"}


def test_deleted_user_is_401(client: TestClient, make_user: Callable[..., AppUser]) -> None:
    user = make_user()
    set_user_deleted(user.id, True)
    res = login(client, user).get("/api-keys")
    assert res.status_code == 401


def test_api_key_alone_is_not_accepted(client: TestClient, make_user: Callable[..., AppUser]) -> None:
    user = make_user()
    issued = login(client, user).post("/api-keys", json={"name": "連携"}).json()
    client.cookies.clear()
    res = client.get("/api-keys", headers={"Authorization": f"Bearer {issued['key']}"})
    assert res.status_code == 401
    res = client.post("/api-keys", json={"name": "増殖"}, headers={"Authorization": f"Bearer {issued['key']}"})
    assert res.status_code == 401
