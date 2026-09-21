from __future__ import annotations

import pytest

from conftest import TestUser, mk_file, mk_folder, mk_part, sql_all, sql_one


@pytest.fixture()
def cl(user: TestUser) -> dict:
    """チェックリストのパーツを持つファイルと、そのチェックリストの識別子。"""
    file_ = mk_file(user, "f", mk_folder(user, "F")["id"])
    part = mk_part(user, file_["id"], "checklist")
    return {"file_id": file_["id"], "part_id": part["id"], "id": part["checklist_id"]}


def url(cl: dict, tail: str = "") -> str:
    return f"/checklists/{cl['id']}{tail}"


def names(state: dict) -> list[str]:
    return [c["name"] for c in state["categories"]]


def titles(state: dict, category: str) -> list[str]:
    return [i["title"] for c in state["categories"] if c["name"] == category for i in c["items"]]


def cat_id(state: dict, name: str) -> int:
    return next(c["id"] for c in state["categories"] if c["name"] == name)


def add_cat(user: TestUser, cl: dict, name: str) -> dict:
    res = user.client.post(url(cl, "/categories"), json={"name": name})
    assert res.status_code == 200, res.text
    return res.json()


def add_item(user: TestUser, cl: dict, title: str, category_id: int | None = None) -> dict:
    body: dict = {"title": title}
    if category_id is not None:
        body["category_id"] = category_id
    res = user.client.post(url(cl, "/items"), json=body)
    assert res.status_code == 200, res.text
    return res.json()


def item_id(state: dict, title: str) -> int:
    return next(i["id"] for c in state["categories"] for i in c["items"] if i["title"] == title)


# ---- 取得・タイトル -------------------------------------------------------------


def test_new_checklist_is_empty(user: TestUser, cl: dict) -> None:
    res = user.client.get(url(cl))
    assert res.status_code == 200
    assert res.json() == {"checklist_id": cl["id"], "title": "", "categories": []}


def test_update_title(user: TestUser, cl: dict) -> None:
    res = user.client.patch(url(cl), json={"title": "  買い物  "})
    assert (res.status_code, res.json()["title"]) == (200, "買い物")
    assert sql_one("SELECT title FROM note_management.checklists WHERE id = %s", (cl["id"],))["title"] == "買い物"
    assert user.client.patch(url(cl), json={"title": ""}).json()["title"] == ""  # 空にもできる
    assert user.client.patch(url(cl), json={}).status_code == 400
    assert user.client.patch(url(cl), json={"title": 5}).status_code == 400


# ---- カテゴリ -----------------------------------------------------------------


def test_add_rename_delete_categories(user: TestUser, cl: dict) -> None:
    state = add_cat(user, cl, " 日用品 ")
    assert names(add_cat(user, cl, "食品")) == ["日用品", "食品"]
    assert all(c["is_unnamed"] is False for c in state["categories"])
    cid = cat_id(state, "日用品")
    res = user.client.patch(url(cl, f"/categories/{cid}"), json={"name": "雑貨"})
    assert (res.status_code, names(res.json())) == (200, ["雑貨", "食品"])
    assert user.client.patch(url(cl, f"/categories/{cid}"), json={"name": "雑貨"}).status_code == 200  # 自身と同じ名前は可
    dup = user.client.patch(url(cl, f"/categories/{cid}"), json={"name": "食品"})
    assert (dup.status_code, dup.json()) == (409, {"detail": "同じ名前のカテゴリがあります"})
    res = user.client.delete(url(cl, f"/categories/{cid}"))
    assert (res.status_code, names(res.json())) == (200, ["食品"])
    assert user.client.delete(url(cl, f"/categories/{cid}")).status_code == 404  # 削除済み
    # 削除済みと同じ名前は付けられる
    assert names(add_cat(user, cl, "雑貨")) == ["食品", "雑貨"]


def test_category_validation(user: TestUser, cl: dict) -> None:
    for body in ({"name": ""}, {"name": "   "}, {}, {"name": 3}):
        assert user.client.post(url(cl, "/categories"), json=body).status_code == 400, body
    add_cat(user, cl, "A")
    res = user.client.post(url(cl, "/categories"), json={"name": "A"})
    assert (res.status_code, res.json()) == (409, {"detail": "同じ名前のカテゴリがあります"})
    state = user.client.get(url(cl)).json()
    assert user.client.patch(url(cl, f"/categories/{cat_id(state, 'A')}"), json={"name": ""}).status_code == 400
    assert user.client.patch(url(cl, "/categories/999999999"), json={"name": "x"}).status_code == 404


def test_reorder_categories(user: TestUser, cl: dict) -> None:
    add_cat(user, cl, "A")
    add_cat(user, cl, "B")
    state = add_cat(user, cl, "C")
    a, b, c = cat_id(state, "A"), cat_id(state, "B"), cat_id(state, "C")
    res = user.client.post(url(cl, "/categories/reorder"), json={"ordered_ids": [c, a, b]})
    assert (res.status_code, names(res.json())) == (200, ["C", "A", "B"])
    assert names(user.client.get(url(cl)).json()) == ["C", "A", "B"]
    for ids, detail in (
        ([a, b], "カテゴリの並びが正しくありません"),
        ([a, b, c, 999999999], "カテゴリの並びが正しくありません"),
        ([], "カテゴリの並びが正しくありません"),
        ([a, a, b], "入力が不正です"),  # 重複
    ):
        res = user.client.post(url(cl, "/categories/reorder"), json={"ordered_ids": ids})
        assert (res.status_code, res.json()) == (400, {"detail": detail}), ids
    assert user.client.post(url(cl, "/categories/reorder"), json={"ordered_ids": ["x"]}).status_code == 400
    assert user.client.post(url(cl, "/categories/reorder"), json={}).status_code == 400
    assert names(user.client.get(url(cl)).json()) == ["C", "A", "B"]  # 失敗したら変わらない


# ---- 項目 ---------------------------------------------------------------------


def test_add_item_without_category_creates_the_unnamed_category(user: TestUser, cl: dict) -> None:
    add_cat(user, cl, "A")
    state = add_item(user, cl, "牛乳")
    assert names(state) == ["", "A"]  # 無名カテゴリが先頭
    assert state["categories"][0]["is_unnamed"] is True
    assert titles(state, "") == ["牛乳"]
    state = add_item(user, cl, "卵")  # 2 回目は、同じ無名カテゴリに入る
    assert (names(state), titles(state, "")) == (["", "A"], ["牛乳", "卵"])
    assert len(sql_all("SELECT id FROM note_management.checklist_categories WHERE checklist_id = %s AND name = ''", (cl["id"],))) == 1
    assert state["categories"][0]["items"][0] == {"id": state["categories"][0]["items"][0]["id"], "title": "牛乳", "is_checked": False}


def test_add_item_to_category_and_title_is_trimmed(user: TestUser, cl: dict) -> None:
    state = add_cat(user, cl, "A")
    state = add_item(user, cl, "  x  ", cat_id(state, "A"))
    assert titles(state, "A") == ["x"]
    state = add_item(user, cl, "", cat_id(state, "A"))  # タイトルが空の項目も作れる
    assert titles(state, "A") == ["x", ""]
    res = user.client.post(url(cl, "/items"), json={})  # 何も指定しなくても、無名カテゴリに空の項目
    assert res.status_code == 200
    assert user.client.post(url(cl, "/items"), json={"category_id": 999999999}).status_code == 404
    assert user.client.post(url(cl, "/items"), json={"category_id": "a"}).status_code == 400


def test_update_item(user: TestUser, cl: dict) -> None:
    state = add_item(user, cl, "牛乳")
    iid = item_id(state, "牛乳")
    res = user.client.patch(url(cl, f"/items/{iid}"), json={"is_checked": True})
    assert (res.status_code, res.json()["categories"][0]["items"][0]) == (200, {"id": iid, "title": "牛乳", "is_checked": True})
    res = user.client.patch(url(cl, f"/items/{iid}"), json={"title": " 豆乳 "})
    assert res.json()["categories"][0]["items"][0] == {"id": iid, "title": "豆乳", "is_checked": True}  # 指定しない項目は変わらない
    res = user.client.patch(url(cl, f"/items/{iid}"), json={"is_checked": False, "title": "x"})
    assert res.json()["categories"][0]["items"][0]["is_checked"] is False
    for body in ({}, {"is_checked": "yes"}, {"title": 1}):
        assert user.client.patch(url(cl, f"/items/{iid}"), json=body).status_code == 400, body
    assert user.client.patch(url(cl, "/items/999999999"), json={"title": "x"}).status_code == 404


def test_delete_item_is_logical(user: TestUser, cl: dict) -> None:
    state = add_item(user, cl, "a")
    state = add_item(user, cl, "b")
    iid = item_id(state, "a")
    res = user.client.delete(url(cl, f"/items/{iid}"))
    assert (res.status_code, titles(res.json(), "")) == (200, ["b"])
    assert sql_one("SELECT is_deleted FROM note_management.checklist_items WHERE id = %s", (iid,))["is_deleted"] is True
    assert user.client.delete(url(cl, f"/items/{iid}")).status_code == 404
    assert user.client.patch(url(cl, f"/items/{iid}"), json={"title": "z"}).status_code == 404


def test_deleting_a_category_deletes_its_items(user: TestUser, cl: dict) -> None:
    state = add_cat(user, cl, "A")
    cid = cat_id(state, "A")
    add_item(user, cl, "x", cid)
    state = add_item(user, cl, "y", cid)
    iid = item_id(state, "x")
    res = user.client.delete(url(cl, f"/categories/{cid}"))
    assert res.json()["categories"] == []
    rows = sql_all("SELECT is_deleted FROM note_management.checklist_items WHERE category_id = %s", (cid,))
    assert [r["is_deleted"] for r in rows] == [True, True]
    assert user.client.patch(url(cl, f"/items/{iid}"), json={"title": "z"}).status_code == 404
    # 無名カテゴリも削除でき、次の項目の追加で、また作られる
    state = add_item(user, cl, "u")
    assert user.client.delete(url(cl, f"/categories/{cat_id(state, '')}")).json()["categories"] == []
    assert names(add_item(user, cl, "u2")) == [""]


def test_move_item_within_and_across_categories(user: TestUser, cl: dict) -> None:
    add_cat(user, cl, "A")
    state = add_cat(user, cl, "B")
    a, b = cat_id(state, "A"), cat_id(state, "B")
    for t in ("a1", "a2", "a3"):
        state = add_item(user, cl, t, a)
    state = add_item(user, cl, "b1", b)
    move = lambda title, to, idx: user.client.post(url(cl, f"/items/{item_id(state, title)}/move"), json={"to_category_id": to, "to_index": idx})  # noqa: E731
    # 同じカテゴリの中で、先頭へ
    res = move("a3", a, 0)
    assert (res.status_code, titles(res.json(), "A")) == (200, ["a3", "a1", "a2"])
    state = res.json()
    # 末尾（件数以上）へ
    state = move("a3", a, 99).json()
    assert titles(state, "A") == ["a1", "a2", "a3"]
    # 別のカテゴリの途中へ。移動元の並びは詰まる
    res = move("a2", b, 0)
    state = res.json()
    assert (titles(state, "A"), titles(state, "B")) == (["a1", "a3"], ["a2", "b1"])
    orders = sql_all("SELECT title, sort_order FROM note_management.checklist_items WHERE checklist_id = %s AND NOT is_deleted ORDER BY category_id, sort_order", (cl["id"],))
    assert [(r["title"], r["sort_order"]) for r in orders] == [("a1", 1), ("a3", 2), ("a2", 1), ("b1", 2)]
    # 無名カテゴリへも移せる
    state = add_item(user, cl, "u")
    unnamed = cat_id(state, "")
    state = move("a1", unnamed, 0).json()
    assert (titles(state, ""), titles(state, "A")) == (["a1", "u"], ["a3"])
    # 失敗
    assert move("a1", 999999999, 0).status_code == 404
    assert user.client.post(url(cl, "/items/999999999/move"), json={"to_category_id": a, "to_index": 0}).status_code == 404
    for body in ({"to_category_id": a, "to_index": -1}, {"to_category_id": a}, {"to_index": 0}, {"to_category_id": a, "to_index": "x"}):
        assert user.client.post(url(cl, f"/items/{item_id(state, 'u')}/move"), json=body).status_code == 400, body


def test_moving_to_a_deleted_category_is_404(user: TestUser, cl: dict) -> None:
    state = add_cat(user, cl, "A")
    a = cat_id(state, "A")
    state = add_item(user, cl, "x")
    user.client.delete(url(cl, f"/categories/{a}"))
    res = user.client.post(url(cl, f"/items/{item_id(state, 'x')}/move"), json={"to_category_id": a, "to_index": 0})
    assert res.status_code == 404


def test_items_of_another_checklist_cannot_be_used(user: TestUser, cl: dict) -> None:
    other_part = mk_part(user, cl["file_id"], "checklist")
    other_cl = {"id": other_part["checklist_id"]}
    state = add_cat(user, other_cl, "X")
    x = cat_id(state, "X")
    state_other = add_item(user, other_cl, "t", x)
    iid = item_id(state_other, "t")
    assert user.client.patch(url(cl, f"/items/{iid}"), json={"title": "z"}).status_code == 404
    assert user.client.delete(url(cl, f"/items/{iid}")).status_code == 404
    assert user.client.post(url(cl, "/items"), json={"category_id": x}).status_code == 404
    assert user.client.patch(url(cl, f"/categories/{x}"), json={"name": "z"}).status_code == 404
    assert user.client.delete(url(cl, f"/categories/{x}")).status_code == 404
    assert titles(user.client.get(f"/checklists/{other_cl['id']}").json(), "X") == ["t"]  # 変わらない


# ---- 他ユーザ・削除済み ------------------------------------------------------------


def test_other_users_get_404_everywhere(user: TestUser, other_user: TestUser, cl: dict) -> None:
    state = add_cat(user, cl, "A")
    a = cat_id(state, "A")
    state = add_item(user, cl, "x", a)
    iid = item_id(state, "x")
    calls = [
        other_user.client.get(url(cl)),
        other_user.client.patch(url(cl), json={"title": "z"}),
        other_user.client.post(url(cl, "/categories"), json={"name": "z"}),
        other_user.client.patch(url(cl, f"/categories/{a}"), json={"name": "z"}),
        other_user.client.delete(url(cl, f"/categories/{a}")),
        other_user.client.post(url(cl, "/categories/reorder"), json={"ordered_ids": [a]}),
        other_user.client.post(url(cl, "/items"), json={"category_id": a}),
        other_user.client.patch(url(cl, f"/items/{iid}"), json={"title": "z"}),
        other_user.client.delete(url(cl, f"/items/{iid}")),
        other_user.client.post(url(cl, f"/items/{iid}/move"), json={"to_category_id": a, "to_index": 0}),
    ]
    assert [c.status_code for c in calls] == [404] * len(calls)
    assert user.client.get("/checklists/999999999").status_code == 404
    assert titles(user.client.get(url(cl)).json(), "A") == ["x"]


def test_changes_to_a_deleted_part_or_file_are_409_but_reading_works(user: TestUser, cl: dict) -> None:
    state = add_item(user, cl, "x")
    iid = item_id(state, "x")
    cid = cat_id(state, "")

    def all_mutations() -> list[int]:
        return [
            user.client.patch(url(cl), json={"title": "z"}).status_code,
            user.client.post(url(cl, "/categories"), json={"name": "n"}).status_code,
            user.client.patch(url(cl, f"/items/{iid}"), json={"is_checked": True}).status_code,
            user.client.delete(url(cl, f"/items/{iid}")).status_code,
            user.client.post(url(cl, "/items"), json={}).status_code,
            user.client.post(url(cl, f"/items/{iid}/move"), json={"to_category_id": cid, "to_index": 0}).status_code,
            user.client.delete(url(cl, f"/categories/{cid}")).status_code,
            user.client.post(url(cl, "/categories/reorder"), json={"ordered_ids": []}).status_code,
        ]

    user.client.delete(f"/parts/{cl['part_id']}")  # パーツが削除済み
    assert all_mutations() == [409] * 8
    res = user.client.patch(url(cl), json={"title": "z"})
    assert res.json() == {"detail": "削除済みのため操作できません"}
    assert user.client.get(url(cl)).status_code == 200  # 取得はできる
    user.client.post(f"/parts/{cl['part_id']}/undelete")
    assert user.client.patch(url(cl), json={"title": "z"}).status_code == 200
    user.client.delete(f"/files/{cl['file_id']}")  # ファイルが削除済み
    assert all_mutations() == [409] * 8
    assert titles(user.client.get(url(cl)).json(), "") == ["x"]  # 何も変わらない


def test_checklist_endpoints_require_login(cl: dict) -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    assert client.get(url(cl)).status_code == 401
    assert client.post(url(cl, "/items"), json={}).status_code == 401
    assert client.delete(url(cl, "/items/1")).status_code == 401
