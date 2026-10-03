"""解約順 API のテスト（REQ-008、REQ-009、REQ-012、REQ-013 / api-design.md 解約順）。"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from conftest import Owner, bearer, execute, insert_category, insert_contract, issue_key


def _contract(c: TestClient, name: str, **fields: Any) -> int:
    res = c.post("/contracts", json={"name": name, **fields})
    assert res.status_code == 201, res.text
    return int(res.json()["id"])


def _save(c: TestClient, ids: list[int]) -> dict[str, Any]:
    res = c.put("/cancellation-plan", json={"contract_ids": ids})
    assert res.status_code == 200, res.text
    return res.json()


def _order(plan: dict[str, Any]) -> list[str]:
    return [i["name"] for i in plan["items"]]


def _db_plan(owner: Owner) -> list[tuple[int, int]]:
    rows = execute(
        "SELECT contract_id, position FROM contract_management.cancellation_plan WHERE user_id = %s ORDER BY position",
        (owner.id,),
    )
    return [(int(r["contract_id"]), int(r["position"])) for r in rows]


def test_empty_by_default(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    c = make_client(make_owner())
    assert c.get("/cancellation-plan").json() == {"items": [], "warnings": []}
    assert _save(c, []) == {"items": [], "warnings": []}


def test_save_and_get_keep_order(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    owner = make_owner()
    c = make_client(owner)
    a = _contract(c, "A", cancellation_method="手順A\n二行目")
    b = _contract(c, "B")
    d = _contract(c, "D", status="paused")
    saved = _save(c, [d, a, b])
    assert _order(saved) == ["D", "A", "B"]
    assert [i["position"] for i in saved["items"]] == [1, 2, 3]
    assert [i["contract_id"] for i in saved["items"]] == [d, a, b]
    assert saved["items"][1]["cancellation_method"] == "手順A\n二行目" and saved["items"][0]["cancellation_method"] is None
    assert c.get("/cancellation-plan").json() == saved  # 再取得しても同じ
    assert _db_plan(owner) == [(d, 1), (a, 2), (b, 3)]
    # 並べ替えと、一部を外す保存（全置き換え）
    assert _order(_save(c, [b, d])) == ["B", "D"]
    assert _db_plan(owner) == [(b, 1), (d, 2)]
    assert _save(c, []) == {"items": [], "warnings": []}
    assert _db_plan(owner) == []


def test_save_validation(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    a_owner = make_owner()
    other = make_owner()
    ca = make_client(a_owner)
    cb = make_client(other)
    ok = _contract(ca, "対象")
    non_contract = _contract(ca, "アカウント", has_contract=False)
    cancelled = _contract(ca, "解約済み", status="cancelled")
    deleted = _contract(ca, "削除済み")
    ca.delete(f"/contracts/{deleted}")
    foreign = _contract(cb, "他人")
    for ids in (
        [ok, ok],  # 重複
        [non_contract],  # 契約を伴わない
        [cancelled],  # ステータスが解約
        [deleted],  # 削除済み
        [foreign],  # 他ユーザ
        [999999999],  # 存在しない
        [ok, foreign],
    ):
        assert ca.put("/cancellation-plan", json={"contract_ids": ids}).status_code == 400, ids
    for body in ({}, {"contract_ids": "1"}, {"contract_ids": ["1"]}, {"contract_ids": [True]}, {"contract_ids": [1], "x": 1}):
        assert ca.put("/cancellation-plan", json=body).status_code == 400, body
    # 失敗した保存は、保存済みの解約順を変えない
    _save(ca, [ok])
    assert ca.put("/cancellation-plan", json={"contract_ids": [ok, foreign]}).status_code == 400
    assert _order(ca.get("/cancellation-plan").json()) == ["対象"]


def test_candidates(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    owner = make_owner()
    c = make_client(owner)
    cat = c.post("/categories", json={"name": "動画配信"}).json()
    in_plan = _contract(c, "計画に入っている")
    a = _contract(c, "有効", category_id=cat["id"], cancellation_method="手順")
    b = _contract(c, "休止中", status="paused")
    _contract(c, "解約済み", status="cancelled")
    _contract(c, "契約を伴わない", has_contract=False)
    deleted = _contract(c, "削除済み")
    c.delete(f"/contracts/{deleted}")
    _save(c, [in_plan])
    items = c.get("/cancellation-plan/candidates").json()["items"]
    assert items == [
        {"id": a, "name": "有効", "category_name": "動画配信", "has_cancellation_method": True},
        {"id": b, "name": "休止中", "category_name": "その他", "has_cancellation_method": False},
    ]


def test_items_drop_contracts_that_no_longer_qualify(
    make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]
) -> None:
    owner = make_owner()
    c = make_client(owner)
    a = _contract(c, "A")
    b = _contract(c, "B")
    d = _contract(c, "D")
    e = _contract(c, "E")
    _save(c, [a, b, d, e])
    # 契約を伴わないに切替・解約・削除は、API が解約順から外す
    assert c.patch(f"/contracts/{a}", json={"name": "A", "has_contract": False}).status_code == 200
    assert c.patch(f"/contracts/{b}", json={"name": "B", "status": "cancelled"}).status_code == 200
    assert _order(c.get("/cancellation-plan").json()) == ["D", "E"]
    assert _db_plan(owner) == [(d, 1), (e, 2)]
    c.delete(f"/contracts/{d}")
    assert _db_plan(owner) == [(e, 1)]
    # API を通さずに行が残っていても（直接の更新）、取得では除かれる
    execute("UPDATE contract_management.contracts SET status = 'cancelled' WHERE id = %s", (e,))
    assert c.get("/cancellation-plan").json() == {"items": [], "warnings": []}


def test_warnings(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    owner = make_owner()
    c = make_client(owner)
    provider = _contract(c, "プロバイダ")
    video = _contract(c, "動画", depends_on_ids=[provider])  # 動画は プロバイダ に依存
    music = _contract(c, "音楽", depends_on_ids=[provider, video])
    outside = _contract(c, "計画外")
    stray = _contract(c, "計画外に依存", depends_on_ids=[outside])
    # 依存先（プロバイダ）が先: 警告
    plan = _save(c, [provider, video])
    assert plan["warnings"] == [
        {"contract_id": video, "name": "動画", "depends_on_contract_id": provider, "depends_on_name": "プロバイダ"}
    ]
    # 依存元（動画）が先: 警告なし
    plan = _save(c, [video, provider])
    assert plan["warnings"] == []
    assert plan["items"][0]["depends_on"] == [{"id": provider, "name": "プロバイダ"}]
    # 複数の依存: 該当をすべて返す（依存元の順、依存先の ID 順）
    plan = _save(c, [provider, video, music])
    assert plan["warnings"] == [
        {"contract_id": video, "name": "動画", "depends_on_contract_id": provider, "depends_on_name": "プロバイダ"},
        {"contract_id": music, "name": "音楽", "depends_on_contract_id": provider, "depends_on_name": "プロバイダ"},
        {"contract_id": music, "name": "音楽", "depends_on_contract_id": video, "depends_on_name": "動画"},
    ]
    # 計画に入っていない契約への依存は、警告にならない
    assert _save(c, [stray])["warnings"] == []
    # 取得でも同じ警告が返る。警告があっても保存はできている
    assert c.get("/cancellation-plan").json() == _save(c, [stray])
    assert len(_db_plan(owner)) == 1


def test_response_has_no_sensitive_fields(
    make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]
) -> None:
    c = make_client(make_owner())
    cid = _contract(
        c, "機微あり", login_methods=["password"], username="secret-user", password="secret-pw",
        registered_email="secret@example.com", cancellation_method="手順",
    )
    saved = _save(c, [cid])
    text = json.dumps([saved, c.get("/cancellation-plan").json(), c.get("/cancellation-plan/candidates").json()], ensure_ascii=False)
    for secret in ("secret-user", "secret-pw", "secret@example.com"):
        assert secret not in text
    assert set(saved["items"][0]) == {"position", "contract_id", "name", "cancellation_method", "depends_on"}


def test_other_users_are_isolated(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    a = make_owner()
    b = make_owner()
    ca = make_client(a)
    cb = make_client(b)
    mine = _contract(ca, "自分")
    _save(ca, [mine])
    assert cb.get("/cancellation-plan").json() == {"items": [], "warnings": []}
    assert cb.get("/cancellation-plan/candidates").json() == {"items": []}
    _save(cb, [])  # 他ユーザの保存は、自分の解約順を変えない
    assert _order(ca.get("/cancellation-plan").json()) == ["自分"]
    # 他ユーザの契約の ID の指定は 400
    assert cb.put("/cancellation-plan", json={"contract_ids": [mine]}).status_code == 400


def test_auth_and_api_key_scope(make_owner: Callable[..., Owner], client: TestClient) -> None:
    for call in (
        lambda: client.get("/cancellation-plan"),
        lambda: client.get("/cancellation-plan/candidates"),
        lambda: client.put("/cancellation-plan", json={"contract_ids": []}),
    ):
        assert call().status_code == 401
    owner = make_owner()
    cat = insert_category(owner, "x")
    cid = insert_contract(owner, cat, "計画", cancellation_method="手順")
    execute(
        "INSERT INTO contract_management.cancellation_plan (user_id, contract_id, position) VALUES (%s, %s, 1)",
        (owner.id, cid),
    )
    headers = bearer(issue_key(owner))
    res = client.get("/cancellation-plan", headers=headers)
    assert res.status_code == 200 and res.json()["items"][0]["contract_id"] == cid
    assert client.get("/cancellation-plan/candidates", headers=headers).status_code == 403
    assert client.put("/cancellation-plan", json={"contract_ids": []}, headers=headers).status_code == 403
    assert _db_plan(owner) == [(cid, 1)]  # 拒否された保存は、何も変えない
