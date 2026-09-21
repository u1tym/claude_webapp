"""材料・分量名称の API（REQ-002・008・009）。"""

from __future__ import annotations

from app.db import get_conn

from conftest import TestUser


def _db_order(sql: str, params: tuple = ()) -> list:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return [r["id"] for r in cur.fetchall()]


def _ingredient_ids_in_db_order(user_id: int) -> list[int]:
    return _db_order(
        "SELECT id FROM recipe_management.ingredients WHERE user_id IS NULL OR user_id = %s ORDER BY kana, id", (user_id,)
    )


def _measurement_ids_in_db_order(user_id: int) -> list[int]:
    return _db_order(
        "SELECT id FROM recipe_management.measurements WHERE user_id IS NULL OR user_id = %s ORDER BY name_bef, name_aft, id",
        (user_id,),
    )


def _names(client, path: str, key: str = "name") -> list[str]:
    return [i[key] for i in client.get(path).json()["items"]]


# ---- 材料 ----------------------------------------------------------------


def test_ingredients_start_with_common_ones_in_kana_order(user: TestUser) -> None:
    items = user.client.get("/ingredients").json()["items"]
    assert all(i["is_system"] for i in items)
    assert len(items) == 12
    assert [i["id"] for i in items] == _ingredient_ids_in_db_order(user.id)  # かなの昇順（同じなら識別子の昇順）
    assert set(items[0]) == {"id", "name", "kana", "is_system"}


def test_add_own_ingredient_and_sort(user: TestUser) -> None:
    res = user.client.post("/ingredients", json={"name": "  大根  ", "kana": " だいこん "})
    assert res.status_code == 201
    body = res.json()
    assert (body["name"], body["kana"], body["is_system"]) == ("大根", "だいこん", False)
    items = user.client.get("/ingredients").json()["items"]
    assert [i["id"] for i in items] == _ingredient_ids_in_db_order(user.id)
    assert body["id"] in [i["id"] for i in items]
    assert len(items) == 13


def test_ingredients_with_same_kana_are_ordered_by_id(user: TestUser) -> None:
    a = user.client.post("/ingredients", json={"name": "アイウ", "kana": "ああ"}).json()["id"]
    b = user.client.post("/ingredients", json={"name": "亜", "kana": "ああ"}).json()["id"]
    ids = [i["id"] for i in user.client.get("/ingredients").json()["items"] if i["kana"] == "ああ"]
    assert ids == [a, b]


def test_duplicate_ingredient_name_is_409(user: TestUser) -> None:
    res = user.client.post("/ingredients", json={"name": "砂糖", "kana": "さとう"})  # 共通と同じ名前
    assert res.status_code == 409
    assert res.json() == {"detail": "同じ名前の材料があります"}
    assert user.client.post("/ingredients", json={"name": "自分の", "kana": "じぶんの"}).status_code == 201
    assert user.client.post("/ingredients", json={"name": "自分の", "kana": "べつ"}).status_code == 409
    assert len(user.client.get("/ingredients").json()["items"]) == 13  # 既存のものは変わらない


def test_own_ingredients_are_private(user: TestUser, other_user: TestUser) -> None:
    user.client.post("/ingredients", json={"name": "秘密の材料", "kana": "ひみつ"})
    assert "秘密の材料" not in _names(other_user.client, "/ingredients")
    assert other_user.client.post("/ingredients", json={"name": "秘密の材料", "kana": "ひみつ"}).status_code == 201


def test_ingredient_validation(user: TestUser) -> None:
    for body in ({}, {"name": "a"}, {"kana": "a"}, {"name": "", "kana": "a"}, {"name": "  ", "kana": "a"},
                 {"name": "a", "kana": ""}, {"name": "a", "kana": "  "}, {"name": 1, "kana": "a"}):
        assert user.client.post("/ingredients", json=body).status_code == 400, body


# ---- 分量名称 -------------------------------------------------------------


def test_measurements_start_with_common_ones_in_order(user: TestUser) -> None:
    items = user.client.get("/measurements").json()["items"]
    assert sorted((m["name_bef"], m["name_aft"], m["ness_amount"], m["is_system"]) for m in items) == sorted(
        [("", "cc", True, True), ("ひとつまみ", "", False, True), ("大さじ", "", True, True), ("小さじ", "", True, True)]
    )
    assert [m["id"] for m in items] == _measurement_ids_in_db_order(user.id)  # 接頭語・接尾語・識別子の順
    assert items[0]["name_bef"] == ""  # 接頭語が空のものが先頭
    assert set(items[0]) == {"id", "name_bef", "name_aft", "ness_amount", "is_system"}


def test_add_own_measurement(user: TestUser) -> None:
    res = user.client.post("/measurements", json={"name_bef": "", "name_aft": " g ", "ness_amount": True})
    assert res.status_code == 201
    body = res.json()
    assert (body["name_bef"], body["name_aft"], body["ness_amount"], body["is_system"]) == ("", "g", True, False)
    items = user.client.get("/measurements").json()["items"]
    assert len(items) == 5
    assert [m["id"] for m in items] == _measurement_ids_in_db_order(user.id)


def test_measurement_prefix_and_suffix_together(user: TestUser) -> None:
    assert user.client.post("/measurements", json={"name_bef": "約", "name_aft": "g", "ness_amount": True}).status_code == 201
    assert user.client.post("/measurements", json={"name_bef": "少々", "name_aft": "", "ness_amount": False}).status_code == 201


def test_duplicate_measurement_pair_is_409(user: TestUser) -> None:
    res = user.client.post("/measurements", json={"name_bef": "大さじ", "name_aft": "", "ness_amount": True})  # 共通
    assert res.status_code == 409
    assert res.json() == {"detail": "同じ分量名称があります"}
    assert user.client.post("/measurements", json={"name_bef": "", "name_aft": "本", "ness_amount": True}).status_code == 201
    assert user.client.post("/measurements", json={"name_bef": "", "name_aft": "本", "ness_amount": False}).status_code == 409
    assert len(user.client.get("/measurements").json()["items"]) == 5


def test_own_measurements_are_private(user: TestUser, other_user: TestUser) -> None:
    user.client.post("/measurements", json={"name_bef": "", "name_aft": "袋", "ness_amount": True})
    assert ("", "袋") not in [(m["name_bef"], m["name_aft"]) for m in other_user.client.get("/measurements").json()["items"]]
    assert other_user.client.post("/measurements", json={"name_bef": "", "name_aft": "袋", "ness_amount": True}).status_code == 201


def test_measurement_validation(user: TestUser) -> None:
    for body in (
        {},
        {"name_bef": "", "name_aft": "", "ness_amount": True},
        {"name_bef": "  ", "name_aft": "  ", "ness_amount": True},
        {"name_bef": "a", "name_aft": "b"},
        {"name_bef": "a", "name_aft": "b", "ness_amount": "yes"},
        {"name_bef": 1, "name_aft": "b", "ness_amount": True},
        {"name_aft": "b", "ness_amount": True},
    ):
        assert user.client.post("/measurements", json=body).status_code == 400, body
