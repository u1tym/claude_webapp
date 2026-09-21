from __future__ import annotations

from conftest import TestUser, items, mk_file, mk_folder, sql_all, sql_one


def orders(user: TestUser, parent_id: int | None) -> dict[str, int]:
    rows = sql_all(
        "SELECT name, sort_order FROM note_management.folders WHERE user_id = %s AND parent_id IS NOT DISTINCT FROM %s",
        (user.id, parent_id),
    )
    return {r["name"]: r["sort_order"] for r in rows}


# ---- 作成 ---------------------------------------------------------------------


def test_create_root_folders_get_increasing_sort_order(user: TestUser) -> None:
    a = mk_folder(user, "A")
    b = mk_folder(user, "  B  ")
    assert a == {"id": a["id"], "parent_id": None, "name": "A", "sort_order": 1, "is_deleted": False, "ancestor_deleted": False}
    assert (b["name"], b["sort_order"]) == ("B", 2)  # 前後の空白は除く
    row = sql_one("SELECT user_id, parent_id, name, sort_order, is_deleted FROM note_management.folders WHERE id = %s", (b["id"],))
    assert row == {"user_id": user.id, "parent_id": None, "name": "B", "sort_order": 2, "is_deleted": False}


def test_create_child_folder(user: TestUser) -> None:
    root = mk_folder(user, "A")
    c1 = mk_folder(user, "c1", root["id"])
    c2 = mk_folder(user, "c2", root["id"])
    assert (c1["parent_id"], c1["sort_order"], c2["sort_order"]) == (root["id"], 1, 2)
    # 親が違えば、並び順は 1 から始まる
    assert mk_folder(user, "c1", mk_folder(user, "B")["id"])["sort_order"] == 1


def test_create_rejects_bad_input(user: TestUser) -> None:
    for body in ({"parent_id": None, "name": ""}, {"parent_id": None, "name": "   "}, {"parent_id": None}, {"name": "x"}, {"parent_id": "a", "name": "x"}):
        res = user.client.post("/folders", json=body)
        assert res.status_code == 400, body
        assert res.json() == {"detail": "入力が不正です"}


def test_create_duplicate_name_is_409_but_deleted_name_is_reusable(user: TestUser) -> None:
    root = mk_folder(user, "A")
    for parent in (None, root["id"]):
        first = mk_folder(user, "dup", parent)
        res = user.client.post("/folders", json={"parent_id": parent, "name": "dup"})
        assert res.status_code == 409
        assert res.json() == {"detail": "同じ名前があります"}
        assert user.client.delete(f"/folders/{first['id']}").status_code == 204
        again = mk_folder(user, "dup", parent)  # 削除済みと同じ名前は登録できる
        assert again["id"] != first["id"]


def test_create_under_missing_other_or_deleted_parent(user: TestUser, other_user: TestUser) -> None:
    theirs = mk_folder(other_user, "X")
    for parent in (999999999, theirs["id"]):
        res = user.client.post("/folders", json={"parent_id": parent, "name": "n"})
        assert res.status_code == 404
        assert res.json() == {"detail": "対象がありません"}
    mine = mk_folder(user, "A")
    child = mk_folder(user, "c", mine["id"])
    assert user.client.delete(f"/folders/{mine['id']}").status_code == 204
    for parent in (mine["id"], child["id"]):  # 上位が削除済みでも同じ
        res = user.client.post("/folders", json={"parent_id": parent, "name": "n2"})
        assert res.status_code == 409
        assert res.json() == {"detail": "削除済みのため操作できません"}


# ---- 名前変更 -----------------------------------------------------------------


def test_rename(user: TestUser, other_user: TestUser) -> None:
    a = mk_folder(user, "A")
    mk_folder(user, "B")
    res = user.client.patch(f"/folders/{a['id']}", json={"name": " A2 "})
    assert res.status_code == 200
    assert res.json()["name"] == "A2"
    assert user.client.patch(f"/folders/{a['id']}", json={"name": "A2"}).status_code == 200  # 自身と同じ名前は可
    dup = user.client.patch(f"/folders/{a['id']}", json={"name": "B"})
    assert (dup.status_code, dup.json()) == (409, {"detail": "同じ名前があります"})
    assert user.client.patch(f"/folders/{a['id']}", json={"name": " "}).status_code == 400
    assert user.client.patch(f"/folders/{a['id']}", json={}).status_code == 400
    assert other_user.client.patch(f"/folders/{a['id']}", json={"name": "z"}).status_code == 404
    assert user.client.patch("/folders/999999999", json={"name": "z"}).status_code == 404


def test_rename_deleted_folder_is_409(user: TestUser) -> None:
    root = mk_folder(user, "A")
    child = mk_folder(user, "c", root["id"])
    user.client.delete(f"/folders/{root['id']}")
    for fid in (root["id"], child["id"]):
        res = user.client.patch(f"/folders/{fid}", json={"name": "z"})
        assert (res.status_code, res.json()) == (409, {"detail": "削除済みのため操作できません"})


# ---- 移動 ---------------------------------------------------------------------


def test_move_goes_to_end_of_destination(user: TestUser) -> None:
    a, b = mk_folder(user, "A"), mk_folder(user, "B")
    mk_folder(user, "x", b["id"])
    c = mk_folder(user, "c", a["id"])
    res = user.client.post(f"/folders/{c['id']}/move", json={"new_parent_id": b["id"]})
    assert res.status_code == 200
    assert (res.json()["parent_id"], res.json()["sort_order"]) == (b["id"], 2)
    assert orders(user, b["id"]) == {"x": 1, "c": 2}
    # ルートへ
    res = user.client.post(f"/folders/{c['id']}/move", json={"new_parent_id": None})
    assert (res.status_code, res.json()["parent_id"], res.json()["sort_order"]) == (200, None, 3)


def test_move_into_self_or_descendant_is_409(user: TestUser) -> None:
    a = mk_folder(user, "A")
    b = mk_folder(user, "B", a["id"])
    c = mk_folder(user, "C", b["id"])
    for target in (a["id"], b["id"], c["id"]):
        res = user.client.post(f"/folders/{a['id']}/move", json={"new_parent_id": target})
        assert (res.status_code, res.json()) == (409, {"detail": "自分の中には移動できません"}), target
    # 子孫でないフォルダへは移動できる
    d = mk_folder(user, "D")
    assert user.client.post(f"/folders/{c['id']}/move", json={"new_parent_id": d["id"]}).status_code == 200


def test_move_to_current_parent_is_409(user: TestUser) -> None:
    a = mk_folder(user, "A")
    c = mk_folder(user, "c", a["id"])
    res = user.client.post(f"/folders/{c['id']}/move", json={"new_parent_id": a["id"]})
    assert (res.status_code, res.json()) == (409, {"detail": "現在の場所と同じです"})
    res = user.client.post(f"/folders/{a['id']}/move", json={"new_parent_id": None})
    assert (res.status_code, res.json()) == (409, {"detail": "現在の場所と同じです"})


def test_move_duplicate_name_at_destination_is_409(user: TestUser) -> None:
    a, b = mk_folder(user, "A"), mk_folder(user, "B")
    mk_folder(user, "same", a["id"])
    other = mk_folder(user, "same", b["id"])
    res = user.client.post(f"/folders/{other['id']}/move", json={"new_parent_id": a["id"]})
    assert (res.status_code, res.json()) == (409, {"detail": "同じ名前があります"})
    assert sql_one("SELECT parent_id FROM note_management.folders WHERE id = %s", (other["id"],))["parent_id"] == b["id"]


def test_move_rejects_missing_other_deleted_and_bad_input(user: TestUser, other_user: TestUser) -> None:
    a, b = mk_folder(user, "A"), mk_folder(user, "B")
    theirs = mk_folder(other_user, "T")
    assert user.client.post(f"/folders/{a['id']}/move", json={}).status_code == 400
    assert user.client.post(f"/folders/{a['id']}/move", json={"new_parent_id": "x"}).status_code == 400
    assert user.client.post(f"/folders/{a['id']}/move", json={"new_parent_id": 999999999}).status_code == 404
    assert user.client.post(f"/folders/{a['id']}/move", json={"new_parent_id": theirs["id"]}).status_code == 404
    assert user.client.post("/folders/999999999/move", json={"new_parent_id": b["id"]}).status_code == 404
    assert other_user.client.post(f"/folders/{a['id']}/move", json={"new_parent_id": theirs["id"]}).status_code == 404
    user.client.delete(f"/folders/{b['id']}")
    res = user.client.post(f"/folders/{a['id']}/move", json={"new_parent_id": b["id"]})  # 削除済みの移動先
    assert (res.status_code, res.json()) == (409, {"detail": "削除済みのため操作できません"})
    res = user.client.post(f"/folders/{b['id']}/move", json={"new_parent_id": a["id"]})  # 削除済みの移動元
    assert (res.status_code, res.json()) == (409, {"detail": "削除済みのため操作できません"})


# ---- 並び替え -----------------------------------------------------------------


def test_swap_order_exchanges_sort_order(user: TestUser) -> None:
    a, b, c = mk_folder(user, "A"), mk_folder(user, "B"), mk_folder(user, "C")
    res = user.client.post("/folders/swap-order", json={"folder_id_1": a["id"], "folder_id_2": c["id"]})
    assert res.status_code == 204
    assert res.content == b""
    assert orders(user, None) == {"A": 3, "B": 2, "C": 1}
    assert [f["name"] for f in items(user)["folders"]] == ["C", "B", "A"]
    # 子の中でも入れ替えられ、-1 が残らない
    p = mk_folder(user, "P")
    x, y = mk_folder(user, "x", p["id"]), mk_folder(user, "y", p["id"])
    assert user.client.post("/folders/swap-order", json={"folder_id_1": x["id"], "folder_id_2": y["id"]}).status_code == 204
    assert orders(user, p["id"]) == {"x": 2, "y": 1}


def test_swap_order_rejections(user: TestUser, other_user: TestUser) -> None:
    a, b = mk_folder(user, "A"), mk_folder(user, "B")
    c = mk_folder(user, "c", a["id"])
    theirs = mk_folder(other_user, "T")
    post = lambda x, y: user.client.post("/folders/swap-order", json={"folder_id_1": x, "folder_id_2": y})  # noqa: E731
    assert post(a["id"], a["id"]).status_code == 400
    assert user.client.post("/folders/swap-order", json={"folder_id_1": a["id"]}).status_code == 400
    res = post(a["id"], c["id"])  # 親が違う
    assert (res.status_code, res.json()) == (400, {"detail": "同じ場所の項目ではありません"})
    assert post(a["id"], theirs["id"]).status_code == 404
    assert post(a["id"], 999999999).status_code == 404
    user.client.delete(f"/folders/{b['id']}")
    res = post(a["id"], b["id"])
    assert (res.status_code, res.json()) == (409, {"detail": "削除済みのため操作できません"})
    assert orders(user, None) == {"A": 1, "B": 2}  # 失敗したら変わらない


# ---- 削除・削除解除 -------------------------------------------------------------


def test_delete_is_logical_and_leaves_descendants_untouched(user: TestUser) -> None:
    a = mk_folder(user, "A")
    b = mk_folder(user, "B", a["id"])
    f = mk_file(user, "f", b["id"])
    res = user.client.delete(f"/folders/{a['id']}")
    assert res.status_code == 204
    assert res.content == b""
    rows = {r["id"]: r["is_deleted"] for r in sql_all("SELECT id, is_deleted FROM note_management.folders WHERE user_id = %s", (user.id,))}
    assert rows == {a["id"]: True, b["id"]: False}  # 子孫の行は変わらない
    assert sql_one("SELECT is_deleted FROM note_management.files WHERE id = %s", (f["id"],))["is_deleted"] is False
    assert items(user)["folders"] == []  # 通常の表示に出ない
    again = user.client.delete(f"/folders/{a['id']}")
    assert (again.status_code, again.json()) == (409, {"detail": "既に削除されています"})


def test_delete_rejects_missing_and_other_users(user: TestUser, other_user: TestUser) -> None:
    a = mk_folder(user, "A")
    assert other_user.client.delete(f"/folders/{a['id']}").status_code == 404
    assert user.client.delete("/folders/999999999").status_code == 404
    assert sql_one("SELECT is_deleted FROM note_management.folders WHERE id = %s", (a["id"],))["is_deleted"] is False


def test_undelete_restores_at_original_position(user: TestUser) -> None:
    a, b, c = mk_folder(user, "A"), mk_folder(user, "B"), mk_folder(user, "C")
    user.client.delete(f"/folders/{b['id']}")
    mk_folder(user, "D")
    res = user.client.post(f"/folders/{b['id']}/undelete")
    assert res.status_code == 200
    assert (res.json()["is_deleted"], res.json()["sort_order"]) == (False, 2)
    assert [f["name"] for f in items(user)["folders"]] == ["A", "B", "C", "D"]
    assert orders(user, None) == {"A": 1, "B": 2, "C": 3, "D": 4}


def test_undelete_rejections(user: TestUser, other_user: TestUser) -> None:
    a = mk_folder(user, "A")
    res = user.client.post(f"/folders/{a['id']}/undelete")
    assert (res.status_code, res.json()) == (409, {"detail": "削除されていません"})
    user.client.delete(f"/folders/{a['id']}")
    mk_folder(user, "A")  # 同名を、削除されていない状態で作る
    res = user.client.post(f"/folders/{a['id']}/undelete")
    assert (res.status_code, res.json()) == (409, {"detail": "同じ名前があります"})
    assert other_user.client.post(f"/folders/{a['id']}/undelete").status_code == 404
    assert user.client.post("/folders/999999999/undelete").status_code == 404


# ---- ツリーの一覧 ---------------------------------------------------------------


def test_items_lists_children_in_order_and_files_only_in_folders(user: TestUser) -> None:
    a = mk_folder(user, "A")
    mk_folder(user, "z", a["id"])
    mk_folder(user, "y", a["id"])
    mk_file(user, "t2", a["id"])
    mk_file(user, "t1", a["id"])
    root = items(user)
    assert root["parent"] is None
    assert root["files"] == []  # ルートの直下にファイルはない
    assert [f["name"] for f in root["folders"]] == ["A"]
    inside = items(user, a["id"])
    assert inside["parent"] == {"id": a["id"], "name": "A", "is_deleted": False, "ancestor_deleted": False}
    assert [f["name"] for f in inside["folders"]] == ["z", "y"]  # 登録順（並び順）
    assert [f["title"] for f in inside["files"]] == ["t2", "t1"]
    assert set(inside["files"][0]) == {"id", "folder_id", "title", "sort_order", "is_deleted", "ancestor_deleted"}


def test_items_hides_deleted_and_flags_ancestor_deleted(user: TestUser) -> None:
    a = mk_folder(user, "A")
    b = mk_folder(user, "B", a["id"])
    c = mk_folder(user, "C", b["id"])
    f = mk_file(user, "f", c["id"])
    mk_folder(user, "D")
    user.client.delete(f"/folders/{a['id']}")
    assert [x["name"] for x in items(user)["folders"]] == ["D"]
    with_deleted = items(user, include_deleted=True)["folders"]
    assert [(x["name"], x["is_deleted"], x["ancestor_deleted"]) for x in with_deleted] == [("A", True, False), ("D", False, False)]
    # 削除済みのフォルダの中身も開ける。上位が削除済みなので、子は ancestor_deleted
    inside = items(user, a["id"], include_deleted=True)
    assert inside["parent"]["is_deleted"] is True
    assert [(x["name"], x["is_deleted"], x["ancestor_deleted"]) for x in inside["folders"]] == [("B", False, True)]
    assert items(user, a["id"])["folders"] == []  # 削除済みを含めない指定では、上位が削除済みのものも出ない
    deep = items(user, c["id"], include_deleted=True)
    assert deep["parent"]["ancestor_deleted"] is True
    assert [(x["title"], x["ancestor_deleted"]) for x in deep["files"]] == [("f", True)]
    assert items(user, c["id"])["files"] == []
    # 上位を削除解除すると、元に戻る
    user.client.post(f"/folders/{a['id']}/undelete")
    assert [x["title"] for x in items(user, c["id"])["files"]] == ["f"]
    assert [x["name"] for x in items(user)["folders"]] == ["A", "D"]
    # 中間のフォルダだけが削除済みのとき、その下は ancestor_deleted、その上は影響なし
    user.client.delete(f"/folders/{b['id']}")
    assert items(user, a["id"])["folders"] == []
    assert items(user, c["id"], include_deleted=True)["files"][0]["ancestor_deleted"] is True


def test_items_rejections(user: TestUser, other_user: TestUser) -> None:
    theirs = mk_folder(other_user, "T")
    assert user.client.get("/items", params={"folder_id": theirs["id"]}).status_code == 404
    assert user.client.get("/items", params={"folder_id": 999999999}).status_code == 404
    assert user.client.get("/items", params={"folder_id": "abc"}).status_code == 400
    assert items(user)["folders"] == []  # 他ユーザのものは出ない
    assert [f["name"] for f in items(other_user)["folders"]] == ["T"]


def test_endpoints_require_login() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    assert client.get("/items").status_code == 401
    assert client.post("/folders", json={"parent_id": None, "name": "x"}).status_code == 401
    assert client.post("/folders/swap-order", json={"folder_id_1": 1, "folder_id_2": 2}).status_code == 401
    assert client.delete("/folders/1").status_code == 401
