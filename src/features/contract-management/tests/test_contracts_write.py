"""契約の登録・更新・削除 API のテスト（REQ-001〜REQ-003、REQ-012、REQ-013 / api-design.md POST・PATCH・DELETE）。"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from conftest import Owner, bearer, execute, insert_category, insert_contract, issue_key


def _post(c: TestClient, **body: Any) -> dict[str, Any]:
    body.setdefault("name", "契約")
    res = c.post("/contracts", json=body)
    assert res.status_code == 201, res.text
    return res.json()


def _row(contract_id: int) -> dict[str, Any]:
    return execute("SELECT * FROM contract_management.contracts WHERE id = %s", (contract_id,))[0]


def _deps(contract_id: int) -> list[int]:
    rows = execute(
        "SELECT depends_on_contract_id AS d FROM contract_management.contract_dependencies "
        "WHERE contract_id = %s ORDER BY 1",
        (contract_id,),
    )
    return [int(r["d"]) for r in rows]


def _plan(owner: Owner) -> list[tuple[int, int]]:
    rows = execute(
        "SELECT contract_id, position FROM contract_management.cancellation_plan WHERE user_id = %s ORDER BY position",
        (owner.id,),
    )
    return [(int(r["contract_id"]), int(r["position"])) for r in rows]


def _add_to_plan(owner: Owner, contract_ids: list[int]) -> None:
    for pos, cid in enumerate(contract_ids, start=1):
        execute(
            "INSERT INTO contract_management.cancellation_plan (user_id, contract_id, position) VALUES (%s, %s, %s)",
            (owner.id, cid, pos),
        )


def _default_category(c: TestClient) -> dict[str, Any]:
    return c.get("/categories").json()["items"][0]


# ---- 登録 ----


def test_create_minimal(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    c = make_client(make_owner())
    body = _post(c, name="  名称だけ  ")
    assert body["name"] == "名称だけ" and body["has_contract"] is True and body["status"] == "active"
    assert body["category"]["name"] == "その他"
    assert body["has_password"] is False and body["password_unset"] is False
    assert body["login_methods"] == [] and body["depends_on"] == [] and body["payment_contract"] is None
    assert c.get(f"/contracts/{body['id']}").json() == body


def test_create_full_with_password_and_relations(
    make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]
) -> None:
    owner = make_owner()
    c = make_client(owner)
    video = c.post("/categories", json={"name": "動画配信"}).json()
    bank = c.post("/categories", json={"name": "銀行", "is_financial": True}).json()
    card = _post(c, name="Aカード", has_contract=False, category_id=bank["id"], login_methods=["password"], username="u0", password="cp")
    provider = _post(c, name="プロバイダ")
    body = _post(
        c,
        name="動画",
        category_id=video["id"],
        status="paused",
        homepage="https://e.com",
        memo="メモ",
        login_methods=["password", "2fa_mail", "2fa_tel"],
        twofa_mail_address="m@e.com",
        twofa_tel_number="090-0000-0000",
        username="taro",
        password="  複数\n行  ",
        registered_email="r@e.com",
        fee_amount=990,
        fee_cycle="monthly",
        renewal_date="2026-11-05",
        contract_date="2020-04",
        contract_date_precision="month",
        trial_end_date="2026-10-31",
        auto_renewal=True,
        holder_name="山田",
        member_number="A-1",
        cancel_notice_days=7,
        cancellation_fee="なし",
        min_term_months=12,
        contact_phone="0120",
        contact_email="s@e.com",
        contact_hours="平日",
        cancellation_method="マイページ",
        depends_on_ids=[provider["id"]],
        payment_contract_id=card["id"],
    )
    assert body["category"]["id"] == video["id"] and body["status"] == "paused"
    assert body["login_methods"] == ["password", "2fa_mail", "2fa_tel"]
    assert body["has_password"] is True and body["password_unset"] is False
    assert body["contract_date"] == "2020-04" and body["fee_amount"] == 990
    assert body["depends_on"] == [{"id": provider["id"], "name": "プロバイダ"}]
    assert body["payment_contract"] == {"id": card["id"], "name": "Aカード"}
    assert "password" not in body and "複数" not in json.dumps(body, ensure_ascii=False)
    row = _row(body["id"])
    assert row["user_id"] == owner.id and row["password"] == "  複数\n行  " and row["contract_date"].isoformat() == "2020-04-01"
    assert c.get(f"/contracts/{body['id']}/password").json() == {"password": "  複数\n行  "}
    assert c.get(f"/contracts/{provider['id']}").json()["depended_by"][0]["id"] == body["id"]
    assert c.get(f"/contracts/{card['id']}").json()["payment_for"][0]["id"] == body["id"]


def test_duplicate_names_allowed(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    c = make_client(make_owner())
    a = _post(c, name="同じ")
    b = _post(c, name="同じ")
    assert a["id"] != b["id"]


def test_password_unset_flag_on_create(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    c = make_client(make_owner())
    body = _post(c, login_methods=["password"], username="u")
    assert body["has_password"] is False and body["password_unset"] is True


def test_create_validation_errors(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    c = make_client(make_owner())
    for body in (
        {"name": ""},
        {"name": "x", "status": "終了"},
        {"name": "x", "fee_amount": 100},
        {"name": "x", "contract_date": "2020", "contract_date_precision": "day"},
        {"name": "x", "end_date": "2026-01-01"},
        {"name": "x", "login_methods": ["2fa_tel"], "twofa_mail_address": "a@b.c"},
        {"name": "x", "password": ""},
        {"name": "x", "unknown": 1},
        {"name": "x", "has_contract": False, "fee_amount": 1, "fee_cycle": "monthly"},
        {"name": "x", "has_contract": False, "depends_on_ids": [1]},
    ):
        assert c.post("/contracts", json=body).status_code == 400, body
    assert c.get("/contracts").json()["total"] == 0


def test_create_non_contract(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    c = make_client(make_owner())
    body = _post(c, name="アカウント", has_contract=False, status="paused", login_methods=["password"], username="u", password="p")
    assert body["has_contract"] is False and body["status"] == "paused"
    assert body["fee_amount"] is None and body["depends_on"] == [] and body["cancellation_method"] is None


def test_category_must_be_own_and_not_deleted(
    make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]
) -> None:
    a = make_owner()
    b = make_owner()
    ca = make_client(a)
    cb = make_client(b)
    foreign = cb.post("/categories", json={"name": "他人"}).json()
    mine = ca.post("/categories", json={"name": "自分"}).json()
    assert ca.post("/contracts", json={"name": "x", "category_id": foreign["id"]}).status_code == 400
    assert ca.post("/contracts", json={"name": "x", "category_id": 999999999}).status_code == 400
    ca.delete(f"/categories/{mine['id']}")
    assert ca.post("/contracts", json={"name": "x", "category_id": mine["id"]}).status_code == 400


def test_dependency_and_payment_targets(
    make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]
) -> None:
    a = make_owner()
    b = make_owner()
    ca = make_client(a)
    cb = make_client(b)
    bank = ca.post("/categories", json={"name": "銀行", "is_financial": True}).json()
    card = _post(ca, name="カード", category_id=bank["id"])
    plain = _post(ca, name="一般")
    foreign = _post(cb, name="他人")
    deleted = _post(ca, name="削除済み", category_id=bank["id"])
    assert ca.delete(f"/contracts/{deleted['id']}").status_code == 204

    def post_status(**fields: Any) -> int:
        return ca.post("/contracts", json={"name": "x", **fields}).status_code

    assert post_status(depends_on_ids=[plain["id"], card["id"]], payment_contract_id=card["id"]) == 201
    assert post_status(depends_on_ids=[foreign["id"]]) == 400
    assert post_status(depends_on_ids=[deleted["id"]]) == 400
    assert post_status(depends_on_ids=[999999999]) == 400
    assert post_status(depends_on_ids=[plain["id"], plain["id"]]) == 400
    assert post_status(payment_contract_id=plain["id"]) == 400  # 金融機関の区分でない
    assert post_status(payment_contract_id=foreign["id"]) == 400
    assert post_status(payment_contract_id=deleted["id"]) == 400
    assert post_status(payment_contract_id=999999999) == 400


# ---- 更新 ----


def test_update_replaces_all_fields_and_keeps_password_when_omitted(
    make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]
) -> None:
    c = make_client(make_owner())
    created = _post(
        c, name="旧", homepage="https://old", memo="旧メモ", login_methods=["password"], username="old", password="oldpw",
        fee_amount=100, fee_cycle="yearly", holder_name="旧名義", depends_on_ids=[],
    )
    cid = created["id"]
    res = c.patch(f"/contracts/{cid}", json={"name": "新", "login_methods": ["password"], "username": "new"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["name"] == "新" and body["username"] == "new"
    # 送らなかった任意項目は空になる
    assert body["homepage"] is None and body["memo"] is None and body["fee_amount"] is None and body["holder_name"] is None
    # password を送らなかったので、保存済みのパスワードは変わらない
    assert body["has_password"] is True
    assert c.get(f"/contracts/{cid}/password").json() == {"password": "oldpw"}
    # password を送ると変わる
    res = c.patch(f"/contracts/{cid}", json={"name": "新", "login_methods": ["password"], "password": "newpw"})
    assert res.status_code == 200
    assert c.get(f"/contracts/{cid}/password").json() == {"password": "newpw"}
    # null は「指定なし」（変えない）、空文字は不可
    assert c.patch(f"/contracts/{cid}", json={"name": "新", "password": None}).status_code == 200
    assert c.get(f"/contracts/{cid}/password").json() == {"password": "newpw"}
    assert c.patch(f"/contracts/{cid}", json={"name": "新", "password": ""}).status_code == 400
    assert c.get(f"/contracts/{cid}/password").json() == {"password": "newpw"}


def test_update_validation_and_not_found(
    make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]
) -> None:
    a = make_owner()
    b = make_owner()
    ca = make_client(a)
    cb = make_client(b)
    created = _post(ca, name="x")
    cid = created["id"]
    assert ca.patch(f"/contracts/{cid}", json={"name": " "}).status_code == 400
    assert ca.patch(f"/contracts/{cid}", json={"name": "y", "status": "bad"}).status_code == 400
    assert ca.patch(f"/contracts/{cid}", json={"name": "y", "depends_on_ids": [cid]}).status_code == 400  # 自分自身
    assert ca.patch(f"/contracts/{cid}", json={"name": "y", "payment_contract_id": cid}).status_code == 400
    assert ca.patch("/contracts/999999999", json={"name": "y"}).status_code == 404
    assert cb.patch(f"/contracts/{cid}", json={"name": "他人が更新"}).status_code == 404
    assert ca.get(f"/contracts/{cid}").json()["name"] == "x"
    ca.delete(f"/contracts/{cid}")
    assert ca.patch(f"/contracts/{cid}", json={"name": "y"}).status_code == 404


def test_switch_to_non_contract_clears_items_and_plan(
    make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]
) -> None:
    owner = make_owner()
    c = make_client(owner)
    dep = _post(c, name="依存先")
    a = _post(c, name="A", fee_amount=1, fee_cycle="monthly", cancellation_method="手順A", depends_on_ids=[dep["id"]])
    b = _post(c, name="B")
    d = _post(c, name="D")
    _add_to_plan(owner, [a["id"], b["id"], d["id"]])
    res = c.patch(f"/contracts/{a['id']}", json={"name": "A", "has_contract": False, "login_methods": ["password"], "username": "u"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["has_contract"] is False and body["fee_amount"] is None and body["cancellation_method"] is None
    assert body["depends_on"] == [] and _deps(a["id"]) == []
    assert body["username"] == "u"
    # 解約順から外れ、残りが連番になる
    assert _plan(owner) == [(b["id"], 1), (d["id"], 2)]
    # 契約を伴わないものに契約の項目は付けられない
    assert c.patch(f"/contracts/{a['id']}", json={"name": "A", "has_contract": False, "fee_amount": 1, "fee_cycle": "monthly"}).status_code == 400
    # 契約を伴うに戻せる
    assert c.patch(f"/contracts/{a['id']}", json={"name": "A", "has_contract": True, "cancellation_method": "新手順"}).json()["cancellation_method"] == "新手順"


def test_cancelled_status_removes_from_plan_and_end_date(
    make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]
) -> None:
    owner = make_owner()
    c = make_client(owner)
    a = _post(c, name="A")
    b = _post(c, name="B")
    _add_to_plan(owner, [a["id"], b["id"]])
    res = c.patch(f"/contracts/{a['id']}", json={"name": "A", "status": "cancelled", "end_date": "2026-09-30"})
    assert res.status_code == 200 and res.json()["end_date"] == "2026-09-30" and res.json()["status"] == "cancelled"
    assert _plan(owner) == [(b["id"], 1)]
    # 解約でなくなると、契約終了日は消える（送れない）
    assert c.patch(f"/contracts/{a['id']}", json={"name": "A", "status": "active", "end_date": "2026-09-30"}).status_code == 400
    res = c.patch(f"/contracts/{a['id']}", json={"name": "A", "status": "paused"})
    assert res.status_code == 200 and res.json()["end_date"] is None
    # 休止中は、解約順に残る
    execute(
        "INSERT INTO contract_management.cancellation_plan (user_id, contract_id, position) VALUES (%s, %s, 2)",
        (owner.id, a["id"]),
    )
    assert c.patch(f"/contracts/{a['id']}", json={"name": "A", "status": "paused"}).status_code == 200
    assert _plan(owner) == [(b["id"], 1), (a["id"], 2)]


def test_dependency_cycle_is_409(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    c = make_client(make_owner())
    a = _post(c, name="A")
    b = _post(c, name="B", depends_on_ids=[a["id"]])  # B は A に依存
    d = _post(c, name="D", depends_on_ids=[b["id"]])  # D は B に依存
    # A が B に依存すると、A→B→A の循環
    assert c.patch(f"/contracts/{a['id']}", json={"name": "A", "depends_on_ids": [b["id"]]}).status_code == 409
    # A が D に依存すると、A→D→B→A の循環
    assert c.patch(f"/contracts/{a['id']}", json={"name": "A", "depends_on_ids": [d["id"]]}).status_code == 409
    assert _deps(a["id"]) == []
    # 循環しない更新は可（B が D 以外に依存、D が A にも依存）
    assert c.patch(f"/contracts/{d['id']}", json={"name": "D", "depends_on_ids": [b["id"], a["id"]]}).status_code == 200
    # 置き換えで古い依存は消える（B の依存を空にすれば、A が B に依存できる）
    assert c.patch(f"/contracts/{b['id']}", json={"name": "B"}).status_code == 200
    assert c.patch(f"/contracts/{a['id']}", json={"name": "A", "depends_on_ids": [b["id"]]}).status_code == 200


def test_dependency_cycle_ignores_deleted_contracts(
    make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]
) -> None:
    c = make_client(make_owner())
    a = _post(c, name="A")
    b = _post(c, name="B", depends_on_ids=[a["id"]])
    c.delete(f"/contracts/{b['id']}")
    # B は削除済みなので、A が B に依存することはできない（400）。経路にも含まれない
    assert c.patch(f"/contracts/{a['id']}", json={"name": "A", "depends_on_ids": [b["id"]]}).status_code == 400


def test_category_change_blocked_when_payment_target(
    make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]
) -> None:
    c = make_client(make_owner())
    bank = c.post("/categories", json={"name": "銀行", "is_financial": True}).json()
    card_cat = c.post("/categories", json={"name": "カード", "is_financial": True}).json()
    plain = c.post("/categories", json={"name": "一般"}).json()
    card = _post(c, name="カード", category_id=bank["id"])
    other_bank = _post(c, name="口座", category_id=bank["id"])
    user = _post(c, name="利用者", payment_contract_id=card["id"])
    # 支払方法になっているカードを、金融機関でない区分へ変えられない
    assert c.patch(f"/contracts/{card['id']}", json={"name": "カード", "category_id": plain["id"]}).status_code == 409
    # 金融機関の別の区分へは変えられる
    res = c.patch(f"/contracts/{card['id']}", json={"name": "カード", "category_id": card_cat["id"]})
    assert res.status_code == 200 and res.json()["category"]["id"] == card_cat["id"]
    assert c.get(f"/contracts/{user['id']}").json()["payment_contract"]["id"] == card["id"]
    # 支払方法になっていない契約は、金融機関でない区分へ変えられる
    assert c.patch(f"/contracts/{other_bank['id']}", json={"name": "口座", "category_id": plain["id"]}).status_code == 200
    # 利用者が削除されれば、変えられる
    c.delete(f"/contracts/{user['id']}")
    assert c.patch(f"/contracts/{card['id']}", json={"name": "カード", "category_id": plain["id"]}).status_code == 200
    # 省略すると「その他」になる（区分の変更）。支払方法に選んでいる契約の区分が金融機関でなくなる更新は、上のとおり 409


# ---- 削除 ----


def test_delete(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    owner = make_owner()
    c = make_client(owner)
    bank = c.post("/categories", json={"name": "銀行", "is_financial": True}).json()
    card = _post(c, name="カード", category_id=bank["id"])
    target = _post(c, name="対象", payment_contract_id=card["id"])
    other = _post(c, name="他", depends_on_ids=[target["id"]])
    third = _post(c, name="三")
    _add_to_plan(owner, [target["id"], other["id"], third["id"]])
    assert c.delete(f"/contracts/{target['id']}").status_code == 204
    assert c.get(f"/contracts/{target['id']}").status_code == 404
    assert target["id"] not in [i["id"] for i in c.get("/contracts").json()["items"]]
    # 記録は残る（削除フラグが立つ）
    assert _row(target["id"])["is_deleted"] is True
    # 参照していた側の表示から外れる
    assert c.get(f"/contracts/{other['id']}").json()["depends_on"] == []
    assert c.get(f"/contracts/{card['id']}").json()["payment_for"] == []
    # 解約順から外れて連番になる
    assert _plan(owner) == [(other["id"], 1), (third["id"], 2)]
    # 参照されている契約も削除できる（依存先・支払方法）
    assert c.delete(f"/contracts/{card['id']}").status_code == 204
    assert c.delete(f"/contracts/{target['id']}").status_code == 404  # 二重の削除
    assert c.delete("/contracts/999999999").status_code == 404


def test_delete_other_users_is_404(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    a = make_client(make_owner())
    b = make_client(make_owner())
    cid = _post(a, name="x")["id"]
    assert b.delete(f"/contracts/{cid}").status_code == 404
    assert a.get(f"/contracts/{cid}").status_code == 200


def test_auth_required(client: TestClient) -> None:
    assert client.post("/contracts", json={"name": "x"}).status_code == 401
    assert client.patch("/contracts/1", json={"name": "x"}).status_code == 401
    assert client.delete("/contracts/1").status_code == 401


# ---- API キー ----


def test_api_key_create_and_update_without_password(
    make_owner: Callable[..., Owner], make_client: Callable[..., TestClient], client: TestClient
) -> None:
    owner = make_owner()
    headers = bearer(issue_key(owner))
    res = client.post("/contracts", json={"name": "AI が登録", "login_methods": ["password"], "username": "u"}, headers=headers)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["has_password"] is False and body["password_unset"] is True
    assert _row(body["id"])["user_id"] == owner.id  # 登録された契約は、キーの持ち主のもの
    # 人があとからパスワードを入力する
    human = make_client(owner)
    assert human.patch(f"/contracts/{body['id']}", json={"name": "AI が登録", "login_methods": ["password"], "username": "u", "password": "human-pw"}).status_code == 200
    # API キーで更新しても、保存済みのパスワードは変わらない
    res = client.patch(f"/contracts/{body['id']}", json={"name": "AI が更新", "login_methods": ["password"], "username": "u2"}, headers=headers)
    assert res.status_code == 200 and res.json()["name"] == "AI が更新" and res.json()["has_password"] is True
    assert human.get(f"/contracts/{body['id']}/password").json() == {"password": "human-pw"}
    assert "human-pw" not in res.text


def test_api_key_with_password_is_400_and_nothing_saved(
    make_owner: Callable[..., Owner], make_client: Callable[..., TestClient], client: TestClient
) -> None:
    owner = make_owner()
    headers = bearer(issue_key(owner))
    for pw in ("secret", "", None):
        res = client.post("/contracts", json={"name": "x", "password": pw}, headers=headers)
        assert res.status_code == 400, pw
    assert make_client(owner).get("/contracts").json()["total"] == 0
    created = client.post("/contracts", json={"name": "x"}, headers=headers).json()
    for pw in ("secret", None):
        assert client.patch(f"/contracts/{created['id']}", json={"name": "y", "password": pw}, headers=headers).status_code == 400
    assert make_client(owner).get(f"/contracts/{created['id']}").json()["name"] == "x"
    assert make_client(owner).get(f"/contracts/{created['id']}/password").json() == {"password": None}


def test_api_key_cannot_delete_or_touch_others(
    make_owner: Callable[..., Owner], make_client: Callable[..., TestClient], client: TestClient
) -> None:
    owner = make_owner()
    other = make_owner()
    headers = bearer(issue_key(owner))
    mine = _post(make_client(owner), name="自分")
    theirs = _post(make_client(other), name="他人")
    assert client.delete(f"/contracts/{mine['id']}", headers=headers).status_code == 403
    assert make_client(owner).get(f"/contracts/{mine['id']}").status_code == 200
    assert client.patch(f"/contracts/{theirs['id']}", json={"name": "乗っ取り"}, headers=headers).status_code == 404
    assert make_client(other).get(f"/contracts/{theirs['id']}").json()["name"] == "他人"
    # 他ユーザの契約・区分を、登録の入力に使えない
    cat = insert_category(other, "他人の区分")
    assert client.post("/contracts", json={"name": "x", "category_id": cat}, headers=headers).status_code == 400
    ref = insert_contract(other, cat, "他人の契約")
    assert client.post("/contracts", json={"name": "x", "depends_on_ids": [ref]}, headers=headers).status_code == 400
