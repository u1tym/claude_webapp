"""区分 API のテスト（REQ-006、REQ-012 / api-design.md 区分）。"""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from conftest import Owner, bearer, execute, issue_key


def _create(c: TestClient, name: str, is_financial: bool = False) -> dict[str, object]:
    res = c.post("/categories", json={"name": name, "is_financial": is_financial})
    assert res.status_code == 201, res.text
    return res.json()


def _names(c: TestClient) -> list[str]:
    return [i["name"] for i in c.get("/categories").json()["items"]]


def _insert_contract(
    owner: Owner, category_id: int, name: str = "c", payment_contract_id: int | None = None
) -> int:
    return int(
        execute(
            """
            INSERT INTO contract_management.contracts (user_id, category_id, name, payment_contract_id)
            VALUES (%s, %s, %s, %s) RETURNING id
            """,
            (owner.id, category_id, name, payment_contract_id),
        )[0]["id"]
    )


def test_list_creates_default_first(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    c = make_client(make_owner())
    items = c.get("/categories").json()["items"]
    assert [(i["name"], i["is_default"], i["is_financial"]) for i in items] == [("その他", True, False)]
    # 2 回目も 1 つのまま
    assert len(c.get("/categories").json()["items"]) == 1


def test_create_and_order(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    c = make_client(make_owner())
    a = _create(c, "  動画配信  ")
    b = _create(c, "銀行", True)
    assert a["name"] == "動画配信" and a["is_financial"] is False and a["is_default"] is False
    assert b["is_financial"] is True
    assert _names(c) == ["その他", "動画配信", "銀行"]


def test_create_validation(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    c = make_client(make_owner())
    for body in (
        {"name": ""},
        {"name": "   "},
        {"name": "あ" * 101},
        {},
        {"name": "x", "is_financial": "true"},
        {"name": 1},
    ):
        assert c.post("/categories", json=body).status_code == 400, body
    assert c.post("/categories", json={"name": "あ" * 100}).status_code == 201


def test_duplicate_name_is_409_but_deleted_name_can_be_reused(
    make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]
) -> None:
    c = make_client(make_owner())
    first = _create(c, "保険")
    assert c.post("/categories", json={"name": "保険"}).status_code == 409
    assert c.post("/categories", json={"name": "その他"}).status_code == 409
    assert c.delete(f"/categories/{first['id']}").status_code == 204
    assert _create(c, "保険")["id"] != first["id"]


def test_same_name_for_other_users(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    a = make_client(make_owner())
    b = make_client(make_owner())
    _create(a, "共通")
    _create(b, "共通")
    assert _names(a) == ["その他", "共通"] and _names(b) == ["その他", "共通"]


def test_update_name_and_financial(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    c = make_client(make_owner())
    cat = _create(c, "旧")
    res = c.patch(f"/categories/{cat['id']}", json={"name": "新", "is_financial": True})
    assert res.status_code == 200
    assert res.json() == {"id": cat["id"], "name": "新", "is_default": False, "is_financial": True}
    assert _names(c) == ["その他", "新"]
    # 同じ名称への更新（自分自身）は可
    assert c.patch(f"/categories/{cat['id']}", json={"name": "新", "is_financial": False}).status_code == 200
    # 他の区分と重複
    other = _create(c, "別")
    assert c.patch(f"/categories/{other['id']}", json={"name": "新"}).status_code == 409
    assert c.patch(f"/categories/{other['id']}", json={"name": " "}).status_code == 400


def test_default_category_is_fixed(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    c = make_client(make_owner())
    default = c.get("/categories").json()["items"][0]
    assert c.patch(f"/categories/{default['id']}", json={"name": "別名"}).status_code == 409
    assert c.patch(f"/categories/{default['id']}", json={"name": "その他", "is_financial": True}).status_code == 409
    assert c.delete(f"/categories/{default['id']}").status_code == 409
    assert _names(c) == ["その他"]


def test_delete_in_use_is_409(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    owner = make_owner()
    c = make_client(owner)
    cat = _create(c, "使用中")
    contract_id = _insert_contract(owner, int(cat["id"]))
    assert c.delete(f"/categories/{cat['id']}").status_code == 409
    # 削除済みの契約だけが使っているときは削除できる
    execute("UPDATE contract_management.contracts SET is_deleted = true WHERE id = %s", (contract_id,))
    assert c.delete(f"/categories/{cat['id']}").status_code == 204
    assert _names(c) == ["その他"]
    # 削除済みの契約は、削除済みの区分を参照し続ける（行は消えない）
    assert execute("SELECT category_id FROM contract_management.contracts WHERE id = %s", (contract_id,))[0][
        "category_id"
    ] == cat["id"]


def test_unflag_financial_blocked_while_used_as_payment(
    make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]
) -> None:
    owner = make_owner()
    c = make_client(owner)
    bank = _create(c, "銀行", True)
    card = _insert_contract(owner, int(bank["id"]), "カード")
    ref = _insert_contract(owner, int(c.get("/categories").json()["items"][0]["id"]), "参照", card)
    assert c.patch(f"/categories/{bank['id']}", json={"name": "銀行", "is_financial": False}).status_code == 409
    # 名称の変更だけ（金融機関のまま）は可
    assert c.patch(f"/categories/{bank['id']}", json={"name": "銀行2", "is_financial": True}).status_code == 200
    # 参照している契約が削除されたら外せる
    execute("UPDATE contract_management.contracts SET is_deleted = true WHERE id = %s", (ref,))
    res = c.patch(f"/categories/{bank['id']}", json={"name": "銀行2", "is_financial": False})
    assert res.status_code == 200 and res.json()["is_financial"] is False


def test_other_users_category_is_404(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    a = make_client(make_owner())
    b = make_client(make_owner())
    cat = _create(a, "秘密")
    assert b.patch(f"/categories/{cat['id']}", json={"name": "x"}).status_code == 404
    assert b.delete(f"/categories/{cat['id']}").status_code == 404
    assert c_not_found(a, 999999999)
    assert _names(a) == ["その他", "秘密"]


def c_not_found(c: TestClient, category_id: int) -> bool:
    return (
        c.patch(f"/categories/{category_id}", json={"name": "x"}).status_code == 404
        and c.delete(f"/categories/{category_id}").status_code == 404
    )


def test_auth_required(client: TestClient) -> None:
    assert client.get("/categories").status_code == 401
    assert client.post("/categories", json={"name": "x"}).status_code == 401


def test_api_key_can_list_only(make_owner: Callable[..., Owner], client: TestClient) -> None:
    owner = make_owner()
    key = issue_key(owner)
    headers = bearer(key)
    res = client.get("/categories", headers=headers)
    assert res.status_code == 200 and res.json()["items"][0]["name"] == "その他"
    assert client.post("/categories", json={"name": "x"}, headers=headers).status_code == 403
    assert client.patch("/categories/1", json={"name": "x"}, headers=headers).status_code == 403
    assert client.delete("/categories/1", headers=headers).status_code == 403
    assert client.get("/categories", headers={"Authorization": "Bearer wak_invalid"}).status_code == 401
