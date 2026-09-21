"""レシピの API（REQ-002〜007・010）。"""

from __future__ import annotations

from app.db import get_conn

from conftest import TestUser, log_text


def _ing(client, name: str) -> int:
    return next(i["id"] for i in client.get("/ingredients").json()["items"] if i["name"] == name)


def _meas(client, bef: str, aft: str) -> int:
    return next(
        m["id"] for m in client.get("/measurements").json()["items"] if (m["name_bef"], m["name_aft"]) == (bef, aft)
    )


def _body(client, name: str = "出汁巻き", kana: str = "だしまき", **overrides):
    body = {
        "name": name,
        "kana": kana,
        "steps": [
            {
                "description": "卵を溶き、調味料を混ぜる。",
                "items": [
                    {"ingredient_id": _ing(client, "卵"), "measurement_id": _meas(client, "", "cc"), "amount": "3"},
                    {"ingredient_id": _ing(client, "塩"), "measurement_id": _meas(client, "ひとつまみ", ""), "amount": ""},
                ],
            },
            {
                "description": "焼く。",
                "items": [{"ingredient_id": _ing(client, "サラダ油"), "measurement_id": _meas(client, "大さじ", ""), "amount": "1"}],
            },
        ],
    }
    body.update(overrides)
    return body


def _create(client, **kw) -> dict:
    res = client.post("/recipes", json=_body(client, **kw))
    assert res.status_code == 201, res.text
    return res.json()


def _rows(sql: str, params: tuple = ()) -> list[dict]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


# ---- 登録・詳細 -----------------------------------------------------------


def test_create_returns_detail_with_numbering(user: TestUser) -> None:
    detail = _create(user.client)
    assert (detail["name"], detail["kana"]) == ("出汁巻き", "だしまき")
    assert [s["step_no"] for s in detail["steps"]] == [1, 2]
    first = detail["steps"][0]
    assert first["description"] == "卵を溶き、調味料を混ぜる。"
    assert [i["item_no"] for i in first["items"]] == [1, 2]
    egg, salt = first["items"]
    assert egg["ingredient"]["name"] == "卵" and egg["ingredient"]["is_system"] is True
    assert (egg["measurement"]["name_bef"], egg["measurement"]["name_aft"], egg["measurement"]["ness_amount"]) == ("", "cc", True)
    assert egg["amount"] == "3"
    assert salt["measurement"]["ness_amount"] is False and salt["amount"] == ""
    assert set(detail) == {"id", "name", "kana", "steps", "created_at", "updated_at"}
    assert user.client.get(f"/recipes/{detail['id']}").json() == detail


def test_names_and_amounts_are_trimmed(user: TestUser) -> None:
    body = _body(user.client, name="  親子丼  ", kana=" おやこどん ")
    body["steps"][0]["description"] = "  混ぜる  "
    body["steps"][0]["items"][0]["amount"] = "  3  "
    detail = user.client.post("/recipes", json=body).json()
    assert (detail["name"], detail["kana"], detail["steps"][0]["description"]) == ("親子丼", "おやこどん", "混ぜる")
    assert detail["steps"][0]["items"][0]["amount"] == "3"


def test_amount_rules_by_measurement(user: TestUser) -> None:
    body = _body(user.client)
    body["steps"][0]["items"][0]["amount"] = ""  # 数量ありの分量名称（cc）で数量が空
    assert user.client.post("/recipes", json=body).status_code == 400
    body["steps"][0]["items"][0]["amount"] = "   "
    assert user.client.post("/recipes", json=body).status_code == 400
    body = _body(user.client)
    body["steps"][0]["items"][1]["amount"] = "9"  # 数量なしの分量名称の数量は、保存しない
    detail = user.client.post("/recipes", json=body).json()
    assert detail["steps"][0]["items"][1]["amount"] == ""


def test_items_keep_input_order_and_steps_may_have_no_items(user: TestUser) -> None:
    sugar, salt, egg = (_ing(user.client, n) for n in ("砂糖", "塩", "卵"))
    tbsp = _meas(user.client, "大さじ", "")
    body = {
        "name": "並び",
        "kana": "ならび",
        "steps": [
            {"description": "材料なしの手順", "items": []},
            {"description": "順に入れる", "items": [
                {"ingredient_id": egg, "measurement_id": tbsp, "amount": "1"},
                {"ingredient_id": sugar, "measurement_id": tbsp, "amount": "2"},
                {"ingredient_id": salt, "measurement_id": tbsp, "amount": "3"},
                {"ingredient_id": sugar, "measurement_id": tbsp, "amount": "4"},  # 同じ材料を複数回
            ]},
        ],
    }
    detail = user.client.post("/recipes", json=body).json()
    assert detail["steps"][0]["items"] == []
    items = detail["steps"][1]["items"]
    assert [i["ingredient"]["name"] for i in items] == ["卵", "砂糖", "塩", "砂糖"]
    assert [i["amount"] for i in items] == ["1", "2", "3", "4"]
    assert [i["item_no"] for i in items] == [1, 2, 3, 4]


def test_create_validation(user: TestUser) -> None:
    good = _body(user.client)
    cases = [
        {"kana": "x", "steps": good["steps"]},
        {"name": "x", "steps": good["steps"]},
        {"name": "", "kana": "x", "steps": good["steps"]},
        {"name": "  ", "kana": "x", "steps": good["steps"]},
        {"name": "x", "kana": " ", "steps": good["steps"]},
        {"name": "x", "kana": "x"},
        {"name": "x", "kana": "x", "steps": []},
        {"name": "x", "kana": "x", "steps": [{"items": []}]},
        {"name": "x", "kana": "x", "steps": [{"description": "  ", "items": []}]},
        {"name": "x", "kana": "x", "steps": [{"description": "d"}]},
        {"name": "x", "kana": "x", "steps": [{"description": "d", "items": [{"measurement_id": 1, "amount": ""}]}]},
        {"name": "x", "kana": "x", "steps": [{"description": "d", "items": [{"ingredient_id": 1, "amount": ""}]}]},
        {"name": "x", "kana": "x", "steps": [{"description": "d", "items": [{"ingredient_id": 1, "measurement_id": 1}]}]},
        {"name": "x", "kana": "x", "steps": [{"description": "d", "items": [{"ingredient_id": "a", "measurement_id": 1, "amount": ""}]}]},
        {"name": 1, "kana": "x", "steps": good["steps"]},
    ]
    for body in cases:
        assert user.client.post("/recipes", json=body).status_code == 400, body
    assert user.client.get("/recipes").json()["items"] == []


def test_masters_of_other_users_or_missing_are_404_and_nothing_is_created(user: TestUser, other_user: TestUser) -> None:
    foreign_ing = other_user.client.post("/ingredients", json={"name": "他人の材料", "kana": "たにん"}).json()["id"]
    foreign_meas = other_user.client.post("/measurements", json={"name_bef": "", "name_aft": "他", "ness_amount": True}).json()["id"]
    for ingredient_id, measurement_id in (
        (foreign_ing, _meas(user.client, "", "cc")),
        (_ing(user.client, "卵"), foreign_meas),
        (99999999, _meas(user.client, "", "cc")),
        (_ing(user.client, "卵"), 99999999),
    ):
        body = _body(user.client)
        body["steps"][1]["items"][0].update(ingredient_id=ingredient_id, measurement_id=measurement_id)
        assert user.client.post("/recipes", json=body).status_code == 404, (ingredient_id, measurement_id)
    assert user.client.get("/recipes").json()["items"] == []
    assert _rows("SELECT id FROM recipe_management.recipes WHERE user_id = %s", (user.id,)) == []


def test_duplicate_name_is_409_and_keeps_existing(user: TestUser) -> None:
    first = _create(user.client)
    res = user.client.post("/recipes", json=_body(user.client, kana="べつ"))
    assert res.status_code == 409
    assert res.json() == {"detail": "同じメニュー名のレシピがあります"}
    assert user.client.get(f"/recipes/{first['id']}").json() == first  # 既存は変わらない
    assert len(user.client.get("/recipes").json()["items"]) == 1


def test_same_name_is_allowed_for_other_users_and_after_deletion(user: TestUser, other_user: TestUser) -> None:
    first = _create(user.client)
    _create(other_user.client)
    assert user.client.delete(f"/recipes/{first['id']}").status_code == 204
    again = _create(user.client)
    assert again["id"] != first["id"]


# ---- 一覧 -----------------------------------------------------------------


def test_list_is_ordered_by_kana_then_id_and_excludes_deleted(user: TestUser) -> None:
    b = _create(user.client, name="B料理", kana="びー")
    a = _create(user.client, name="A料理", kana="えー")
    same1 = _create(user.client, name="同かな1", kana="おなじ")
    same2 = _create(user.client, name="同かな2", kana="おなじ")
    gone = _create(user.client, name="消す", kana="あ")
    user.client.delete(f"/recipes/{gone['id']}")
    items = user.client.get("/recipes").json()["items"]
    assert set(items[0]) == {"id", "name", "kana"}
    expected = [r["id"] for r in _rows(
        "SELECT id FROM recipe_management.recipes WHERE user_id = %s AND is_deleted = false ORDER BY kana, id", (user.id,)
    )]
    assert [i["id"] for i in items] == expected
    same = [i["id"] for i in items if i["kana"] == "おなじ"]
    assert same == [same1["id"], same2["id"]]
    assert {a["id"], b["id"]} <= set(expected) and gone["id"] not in expected


def test_list_is_private(user: TestUser, other_user: TestUser) -> None:
    _create(user.client)
    assert other_user.client.get("/recipes").json()["items"] == []


# ---- 詳細（対象なし） ------------------------------------------------------


def test_get_other_users_deleted_or_missing_recipe_is_404(user: TestUser, other_user: TestUser) -> None:
    mine = _create(user.client)
    assert other_user.client.get(f"/recipes/{mine['id']}").status_code == 404
    assert user.client.get("/recipes/99999999").status_code == 404
    user.client.delete(f"/recipes/{mine['id']}")
    assert user.client.get(f"/recipes/{mine['id']}").status_code == 404


# ---- 更新 -----------------------------------------------------------------


def test_update_replaces_content_and_keeps_identity(user: TestUser) -> None:
    created = _create(user.client)
    body = _body(user.client, name="出汁巻き卵", kana="だしまきたまご")
    body["steps"] = [{"description": "全部まとめて焼く", "items": [
        {"ingredient_id": _ing(user.client, "砂糖"), "measurement_id": _meas(user.client, "小さじ", ""), "amount": "1/2"}]}]
    res = user.client.put(f"/recipes/{created['id']}", json=body)
    assert res.status_code == 200, res.text
    updated = res.json()
    assert updated["id"] == created["id"]
    assert updated["created_at"] == created["created_at"]
    assert updated["updated_at"] > created["updated_at"]
    assert (updated["name"], updated["kana"]) == ("出汁巻き卵", "だしまきたまご")
    assert len(updated["steps"]) == 1 and updated["steps"][0]["items"][0]["ingredient"]["name"] == "砂糖"
    assert user.client.get(f"/recipes/{created['id']}").json() == updated
    # 名前を変えても、別のレシピも、削除済みのレシピも増えない
    rows = _rows("SELECT id, is_deleted FROM recipe_management.recipes WHERE user_id = %s", (user.id,))
    assert rows == [{"id": created["id"], "is_deleted": False}]
    # 古い工程・材料の行は残らない
    assert _rows(
        "SELECT count(*) AS n FROM recipe_management.recipe_steps WHERE recipe_id = %s", (created["id"],)
    )[0]["n"] == 1


def test_update_with_same_name_is_allowed(user: TestUser) -> None:
    created = _create(user.client)
    res = user.client.put(f"/recipes/{created['id']}", json=_body(user.client, kana="かなだけ変更"))
    assert res.status_code == 200
    assert res.json()["kana"] == "かなだけ変更"


def test_update_to_other_active_recipe_name_is_409_and_keeps_original(user: TestUser) -> None:
    a = _create(user.client, name="A", kana="あ")
    b = _create(user.client, name="B", kana="い")
    res = user.client.put(f"/recipes/{b['id']}", json=_body(user.client, name="A", kana="変更"))
    assert res.status_code == 409
    assert res.json() == {"detail": "同じメニュー名のレシピがあります"}
    assert user.client.get(f"/recipes/{b['id']}").json() == b  # 元の内容が残る
    assert user.client.get(f"/recipes/{a['id']}").json() == a
    # 削除済みの名前へは変更できる
    user.client.delete(f"/recipes/{a['id']}")
    assert user.client.put(f"/recipes/{b['id']}", json=_body(user.client, name="A", kana="い")).status_code == 200


def test_failed_update_rolls_back(user: TestUser, other_user: TestUser) -> None:
    created = _create(user.client)
    foreign = other_user.client.post("/ingredients", json={"name": "他人の", "kana": "たにん"}).json()["id"]
    body = _body(user.client, name="変更後の名前")
    body["steps"][1]["items"][0]["ingredient_id"] = foreign
    assert user.client.put(f"/recipes/{created['id']}", json=body).status_code == 404
    assert user.client.get(f"/recipes/{created['id']}").json() == created  # 名前も工程も元のまま
    body = _body(user.client)
    body["steps"][0]["items"][0]["amount"] = ""
    assert user.client.put(f"/recipes/{created['id']}", json=body).status_code == 400
    assert user.client.get(f"/recipes/{created['id']}").json() == created


def test_update_validation_and_not_found(user: TestUser, other_user: TestUser) -> None:
    created = _create(user.client)
    for bad in ({"name": "", "kana": "x", "steps": _body(user.client)["steps"]}, {"name": "x", "kana": "x", "steps": []}, {}):
        assert user.client.put(f"/recipes/{created['id']}", json=bad).status_code == 400, bad
    body = _body(user.client, name="他人が更新")
    assert other_user.client.put(f"/recipes/{created['id']}", json=_body(other_user.client)).status_code == 404
    assert user.client.put("/recipes/99999999", json=body).status_code == 404
    user.client.delete(f"/recipes/{created['id']}")
    assert user.client.put(f"/recipes/{created['id']}", json=body).status_code == 404  # 削除済み


# ---- 削除 -----------------------------------------------------------------


def test_delete_is_logical_and_removes_from_views(user: TestUser) -> None:
    created = _create(user.client)
    assert user.client.delete(f"/recipes/{created['id']}").status_code == 204
    assert user.client.get("/recipes").json()["items"] == []
    assert user.client.get(f"/recipes/{created['id']}").status_code == 404
    assert user.client.delete(f"/recipes/{created['id']}").status_code == 404  # 二重の削除
    row = _rows("SELECT is_deleted FROM recipe_management.recipes WHERE id = %s", (created["id"],))
    assert row == [{"is_deleted": True}]  # 記録は残る
    assert _rows(
        "SELECT count(*) AS n FROM recipe_management.recipe_steps WHERE recipe_id = %s", (created["id"],)
    )[0]["n"] == 2  # 工程・材料は残る


def test_delete_other_users_or_missing_is_404(user: TestUser, other_user: TestUser) -> None:
    created = _create(user.client)
    assert other_user.client.delete(f"/recipes/{created['id']}").status_code == 404
    assert user.client.delete("/recipes/99999999").status_code == 404
    assert user.client.get(f"/recipes/{created['id']}").status_code == 200


# ---- ログ -----------------------------------------------------------------


def test_operations_are_logged_without_step_descriptions(user: TestUser, log_dir) -> None:
    body = _body(user.client, name="ログ用レシピ")
    body["steps"][0]["description"] = "誰にも見せない手順の本文XYZ"
    created = user.client.post("/recipes", json=body).json()
    user.client.get("/recipes")
    user.client.get(f"/recipes/{created['id']}")
    user.client.put(f"/recipes/{created['id']}", json=body)
    user.client.post("/recipes", json=body)  # 重複
    user.client.delete(f"/recipes/{created['id']}")
    text = log_text(log_dir)
    for expected in (
        "レシピ登録要求", "name=ログ用レシピ", "工程数=2", "材料の行=3", "レシピ登録成功", "レシピ一覧", "レシピ詳細",
        "レシピ更新要求", "レシピ更新成功", "メニュー名重複", "レシピ削除要求", "レシピ削除成功",
    ):
        assert expected in text, expected
    assert "誰にも見せない手順の本文XYZ" not in text
    assert user.client.cookies.get("session_id") not in text
