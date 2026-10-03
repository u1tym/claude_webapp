"""API キーの権限のテスト（REQ-013 / api-design.md のエンドポイント一覧の「API キー」列）。

可のエンドポイントは動き、不可のものは 403 になる。パスワードの値は、入出力のどこにも現れない。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from conftest import Owner, bearer, execute, insert_category, insert_contract, issue_key

FORBIDDEN = {"detail": "権限がありません"}


class Fixture:
    def __init__(self, owner: Owner, contract_id: int, category_id: int, plan_contract_id: int) -> None:
        self.owner = owner
        self.contract_id = contract_id
        self.category_id = category_id
        self.plan_contract_id = plan_contract_id


@pytest.fixture()
def fx(make_owner: Callable[..., Owner]) -> Fixture:
    owner = make_owner()
    cat = insert_category(owner, "動画")
    cid = insert_contract(owner, cat, "既存", login_password=True, username="u", password="S3cret-Pass")
    plan_id = insert_contract(owner, cat, "計画", cancellation_method="手順")
    execute(
        "INSERT INTO contract_management.cancellation_plan (user_id, contract_id, position) VALUES (%s, %s, 1)",
        (owner.id, plan_id),
    )
    return Fixture(owner, cid, cat, plan_id)


def _calls(fx: Fixture) -> list[tuple[str, str, dict[str, Any] | None, int | None]]:
    """(メソッド, パス, 本文, 可のときの期待ステータス)。None は 403（不可）。"""
    c = fx.contract_id
    return [
        ("GET", "/settings", None, 200),
        ("GET", "/accounts", None, None),
        ("GET", "/contracts", None, 200),
        ("GET", f"/contracts/{c}", None, 200),
        ("GET", f"/contracts/{c}/password", None, None),
        ("POST", "/contracts", {"name": "AI 登録"}, 201),
        ("PATCH", f"/contracts/{c}", {"name": "AI 更新"}, 200),
        ("DELETE", f"/contracts/{c}", None, None),
        ("GET", "/categories", None, 200),
        ("POST", "/categories", {"name": "x"}, None),
        ("PATCH", f"/categories/{fx.category_id}", {"name": "y"}, None),
        ("DELETE", f"/categories/{fx.category_id}", None, None),
        ("GET", "/cancellation-plan", None, 200),
        ("GET", "/cancellation-plan/candidates", None, None),
        ("PUT", "/cancellation-plan", {"contract_ids": []}, None),
    ]


def test_every_endpoint_follows_the_api_key_column(fx: Fixture, client: TestClient) -> None:
    headers = bearer(issue_key(fx.owner))
    for method, path, body, expected in _calls(fx):
        res = client.request(method, path, json=body, headers=headers)
        if expected is None:
            assert res.status_code == 403 and res.json() == FORBIDDEN, (method, path, res.status_code)
        else:
            assert res.status_code == expected, (method, path, res.status_code, res.text)


def test_forbidden_calls_change_nothing(fx: Fixture, client: TestClient) -> None:
    headers = bearer(issue_key(fx.owner))
    for method, path, body, expected in _calls(fx):
        if expected is None:
            client.request(method, path, json=body, headers=headers)
    assert execute("SELECT is_deleted, name FROM contract_management.contracts WHERE id = %s", (fx.contract_id,))[0] == {
        "is_deleted": False,
        "name": "既存",
    }
    assert execute("SELECT name, is_deleted FROM contract_management.categories WHERE id = %s", (fx.category_id,))[0] == {
        "name": "動画",
        "is_deleted": False,
    }
    plan = execute("SELECT contract_id FROM contract_management.cancellation_plan WHERE user_id = %s", (fx.owner.id,))
    assert [r["contract_id"] for r in plan] == [fx.plan_contract_id]


def test_same_endpoints_work_with_cookie(fx: Fixture, make_client: Callable[..., TestClient]) -> None:
    """不可の操作は、API キーだけが拒否される。Cookie（人）では動く。"""
    c = make_client(fx.owner)
    assert c.get("/accounts").status_code == 200
    assert c.get(f"/contracts/{fx.contract_id}/password").json() == {"password": "S3cret-Pass"}
    assert c.get("/cancellation-plan/candidates").status_code == 200
    assert c.put("/cancellation-plan", json={"contract_ids": []}).status_code == 200
    assert c.post("/categories", json={"name": "新区分"}).status_code == 201
    assert c.delete(f"/contracts/{fx.contract_id}").status_code == 204


def test_password_is_never_written_or_returned_via_api_key(fx: Fixture, client: TestClient, make_client: Callable[..., TestClient]) -> None:
    headers = bearer(issue_key(fx.owner))
    # 入力: password を含む登録・更新は 400（null・空文字を含む）で、何も保存しない
    before = execute("SELECT count(*) AS n FROM contract_management.contracts WHERE user_id = %s", (fx.owner.id,))[0]["n"]
    for value in ("new-pass", "", None):
        assert client.post("/contracts", json={"name": "x", "password": value}, headers=headers).status_code == 400
        assert client.patch(f"/contracts/{fx.contract_id}", json={"name": "x", "password": value}, headers=headers).status_code == 400
    after = execute("SELECT count(*) AS n FROM contract_management.contracts WHERE user_id = %s", (fx.owner.id,))[0]["n"]
    assert before == after
    assert execute("SELECT password FROM contract_management.contracts WHERE id = %s", (fx.contract_id,))[0]["password"] == "S3cret-Pass"
    # 更新しても、保存済みのパスワードは変わらない（消えも、書き換わりもしない）
    assert client.patch(f"/contracts/{fx.contract_id}", json={"name": "改名", "login_methods": ["password"]}, headers=headers).status_code == 200
    assert execute("SELECT password FROM contract_management.contracts WHERE id = %s", (fx.contract_id,))[0]["password"] == "S3cret-Pass"
    # API キーで登録した契約は、パスワードが未設定
    created = client.post("/contracts", json={"name": "AI", "login_methods": ["password"]}, headers=headers).json()
    assert execute("SELECT password FROM contract_management.contracts WHERE id = %s", (created["id"],))[0]["password"] is None
    assert created["has_password"] is False and created["password_unset"] is True
    # 出力: どの応答にも、パスワードの値がない
    texts = [
        client.get(path, headers=headers).text
        for path in ("/contracts", f"/contracts/{fx.contract_id}", "/categories", "/cancellation-plan", "/settings")
    ]
    assert all("S3cret-Pass" not in t for t in texts)
    assert '"password":' not in "".join(texts).replace('"has_password":', "").replace('"password_unset":', "")


def test_api_key_is_limited_to_its_owner(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient], client: TestClient) -> None:
    a = make_owner()
    b = make_owner()
    mine = make_client(a).post("/contracts", json={"name": "A の契約"}).json()
    theirs = make_client(b).post("/contracts", json={"name": "B の契約"}).json()
    headers = bearer(issue_key(a))
    listed = client.get("/contracts", headers=headers).json()
    assert [i["id"] for i in listed["items"]] == [mine["id"]]
    assert client.get(f"/contracts/{theirs['id']}", headers=headers).status_code == 404
    assert client.patch(f"/contracts/{theirs['id']}", json={"name": "乗っ取り"}, headers=headers).status_code == 404
    assert make_client(b).get(f"/contracts/{theirs['id']}").json()["name"] == "B の契約"
    # 登録される契約は、キーの持ち主のもの
    created = client.post("/contracts", json={"name": "キーで登録"}, headers=headers).json()
    assert execute("SELECT user_id FROM contract_management.contracts WHERE id = %s", (created["id"],))[0]["user_id"] == a.id
    # 他ユーザの区分・契約は、入力に使えない
    cat_b = insert_category(b, "B の区分")
    assert client.post("/contracts", json={"name": "x", "category_id": cat_b}, headers=headers).status_code == 400
    assert client.post("/contracts", json={"name": "x", "depends_on_ids": [theirs["id"]]}, headers=headers).status_code == 400


@pytest.mark.parametrize("state", ["revoked", "expired", "unassigned", "deleted_user"])
def test_unusable_keys_cannot_do_anything(
    make_owner: Callable[..., Owner], client: TestClient, state: str
) -> None:
    from datetime import timedelta

    owner = make_owner(assigned=state != "unassigned")
    key = issue_key(owner, revoked=state == "revoked", expires_in=timedelta(minutes=-1) if state == "expired" else None)
    if state == "deleted_user":
        execute("UPDATE public.users SET is_deleted = true WHERE id = %s", (owner.id,))
    expected = 403 if state == "unassigned" else 401
    headers = bearer(key)
    assert client.get("/contracts", headers=headers).status_code == expected
    assert client.post("/contracts", json={"name": "x"}, headers=headers).status_code == expected
    assert client.get("/cancellation-plan", headers=headers).status_code == expected
    if state != "deleted_user":
        assert execute("SELECT count(*) AS n FROM contract_management.contracts WHERE user_id = %s", (owner.id,))[0]["n"] == 0


def test_forbidden_responses_do_not_leak(fx: Fixture, client: TestClient) -> None:
    headers = bearer(issue_key(fx.owner))
    res = client.get(f"/contracts/{fx.contract_id}/password", headers=headers)
    assert res.status_code == 403 and "S3cret-Pass" not in json.dumps(res.json())
