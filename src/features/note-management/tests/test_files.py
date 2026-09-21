from __future__ import annotations

from conftest import TestUser, items, mk_file, mk_folder, sql_all, sql_one


def file_orders(folder_id: int) -> dict[str, int]:
    rows = sql_all("SELECT title, sort_order FROM note_management.files WHERE folder_id = %s", (folder_id,))
    return {r["title"]: r["sort_order"] for r in rows}


def test_create_file_in_folder(user: TestUser) -> None:
    folder = mk_folder(user, "F")
    a = mk_file(user, "a", folder["id"])
    b = mk_file(user, "  b  ", folder["id"])
    assert a == {"id": a["id"], "folder_id": folder["id"], "title": "a", "sort_order": 1, "is_deleted": False, "ancestor_deleted": False}
    assert (b["title"], b["sort_order"]) == ("b", 2)
    row = sql_one("SELECT user_id, folder_id, is_deleted FROM note_management.files WHERE id = %s", (b["id"],))
    assert row == {"user_id": user.id, "folder_id": folder["id"], "is_deleted": False}
    # 別のフォルダでは、並び順は 1 から始まり、同じタイトルも作れる
    other = mk_file(user, "a", mk_folder(user, "G")["id"])
    assert other["sort_order"] == 1


def test_create_rejections(user: TestUser, other_user: TestUser) -> None:
    folder = mk_folder(user, "F")
    theirs = mk_folder(other_user, "T")
    bodies = (
        {"folder_id": folder["id"], "title": ""},
        {"folder_id": folder["id"], "title": " "},
        {"folder_id": folder["id"]},
        {"title": "x"},
        {"folder_id": None, "title": "x"},  # ルートの直下（フォルダの外）には作れない
    )
    for body in bodies:
        res = user.client.post("/files", json=body)
        assert (res.status_code, res.json()) == (400, {"detail": "入力が不正です"}), body
    assert user.client.post("/files", json={"folder_id": 999999999, "title": "x"}).status_code == 404
    assert user.client.post("/files", json={"folder_id": theirs["id"], "title": "x"}).status_code == 404
    mk_file(user, "dup", folder["id"])
    res = user.client.post("/files", json={"folder_id": folder["id"], "title": "dup"})
    assert (res.status_code, res.json()) == (409, {"detail": "同じタイトルがあります"})


def test_create_in_deleted_folder_is_409(user: TestUser) -> None:
    a = mk_folder(user, "A")
    b = mk_folder(user, "B", a["id"])
    user.client.delete(f"/folders/{a['id']}")
    for fid in (a["id"], b["id"]):
        res = user.client.post("/files", json={"folder_id": fid, "title": "x"})
        assert (res.status_code, res.json()) == (409, {"detail": "削除済みのため操作できません"})


def test_deleted_title_can_be_reused(user: TestUser) -> None:
    folder = mk_folder(user, "F")
    first = mk_file(user, "t", folder["id"])
    assert user.client.delete(f"/files/{first['id']}").status_code == 204
    again = mk_file(user, "t", folder["id"])
    assert again["id"] != first["id"]
    assert again["sort_order"] == 2  # 削除済みも並び順を占める


def test_rename_file(user: TestUser, other_user: TestUser) -> None:
    folder = mk_folder(user, "F")
    a = mk_file(user, "a", folder["id"])
    mk_file(user, "b", folder["id"])
    res = user.client.patch(f"/files/{a['id']}", json={"title": " a2 "})
    assert (res.status_code, res.json()["title"]) == (200, "a2")
    assert user.client.patch(f"/files/{a['id']}", json={"title": "a2"}).status_code == 200
    dup = user.client.patch(f"/files/{a['id']}", json={"title": "b"})
    assert (dup.status_code, dup.json()) == (409, {"detail": "同じタイトルがあります"})
    assert user.client.patch(f"/files/{a['id']}", json={"title": " "}).status_code == 400
    assert other_user.client.patch(f"/files/{a['id']}", json={"title": "z"}).status_code == 404
    user.client.delete(f"/files/{a['id']}")
    res = user.client.patch(f"/files/{a['id']}", json={"title": "z"})
    assert (res.status_code, res.json()) == (409, {"detail": "削除済みのため操作できません"})


def test_move_file_goes_to_end(user: TestUser) -> None:
    f1, f2 = mk_folder(user, "F1"), mk_folder(user, "F2")
    mk_file(user, "x", f2["id"])
    a = mk_file(user, "a", f1["id"])
    res = user.client.post(f"/files/{a['id']}/move", json={"new_folder_id": f2["id"]})
    assert res.status_code == 200
    assert (res.json()["folder_id"], res.json()["sort_order"]) == (f2["id"], 2)
    assert file_orders(f2["id"]) == {"x": 1, "a": 2}
    assert file_orders(f1["id"]) == {}


def test_move_file_rejections(user: TestUser, other_user: TestUser) -> None:
    f1, f2 = mk_folder(user, "F1"), mk_folder(user, "F2")
    theirs = mk_folder(other_user, "T")
    a = mk_file(user, "a", f1["id"])
    mk_file(user, "a", f2["id"])

    def move(file_id: int, dst: int | None):
        return user.client.post(f"/files/{file_id}/move", json={"new_folder_id": dst})

    assert move(a["id"], None).status_code == 400  # ルートへは移せない
    assert user.client.post(f"/files/{a['id']}/move", json={}).status_code == 400
    assert move(a["id"], 999999999).status_code == 404
    assert move(a["id"], theirs["id"]).status_code == 404
    assert move(999999999, f2["id"]).status_code == 404
    res = move(a["id"], f1["id"])
    assert (res.status_code, res.json()) == (409, {"detail": "現在の場所と同じです"})
    res = move(a["id"], f2["id"])
    assert (res.status_code, res.json()) == (409, {"detail": "同じタイトルがあります"})
    user.client.delete(f"/folders/{f2['id']}")
    res = move(a["id"], f2["id"])
    assert (res.status_code, res.json()) == (409, {"detail": "削除済みのため操作できません"})


def test_swap_file_order(user: TestUser) -> None:
    folder = mk_folder(user, "F")
    a, b, c = (mk_file(user, t, folder["id"]) for t in "abc")
    res = user.client.post("/files/swap-order", json={"file_id_1": a["id"], "file_id_2": c["id"]})
    assert (res.status_code, res.content) == (204, b"")
    assert file_orders(folder["id"]) == {"a": 3, "b": 2, "c": 1}
    assert [f["title"] for f in items(user, folder["id"])["files"]] == ["c", "b", "a"]


def test_swap_file_order_rejections(user: TestUser, other_user: TestUser) -> None:
    f1, f2 = mk_folder(user, "F1"), mk_folder(user, "F2")
    a, b = mk_file(user, "a", f1["id"]), mk_file(user, "b", f1["id"])
    c = mk_file(user, "c", f2["id"])
    theirs = mk_file(other_user, "t", mk_folder(other_user, "T")["id"])

    def post(x: int, y: int):
        return user.client.post("/files/swap-order", json={"file_id_1": x, "file_id_2": y})

    assert post(a["id"], a["id"]).status_code == 400
    res = post(a["id"], c["id"])
    assert (res.status_code, res.json()) == (400, {"detail": "同じ場所の項目ではありません"})
    assert post(a["id"], theirs["id"]).status_code == 404
    user.client.delete(f"/files/{b['id']}")
    res = post(a["id"], b["id"])
    assert (res.status_code, res.json()) == (409, {"detail": "削除済みのため操作できません"})
    assert file_orders(f1["id"]) == {"a": 1, "b": 2}


def test_delete_and_undelete_file(user: TestUser, other_user: TestUser) -> None:
    folder = mk_folder(user, "F")
    a = mk_file(user, "a", folder["id"])
    assert other_user.client.delete(f"/files/{a['id']}").status_code == 404
    assert user.client.post(f"/files/{a['id']}/undelete").status_code == 409  # 削除されていない
    res = user.client.delete(f"/files/{a['id']}")
    assert (res.status_code, res.content) == (204, b"")
    assert items(user, folder["id"])["files"] == []
    assert items(user, folder["id"], include_deleted=True)["files"][0]["is_deleted"] is True
    again = user.client.delete(f"/files/{a['id']}")
    assert (again.status_code, again.json()) == (409, {"detail": "既に削除されています"})
    res = user.client.post(f"/files/{a['id']}/undelete")
    assert res.status_code == 200
    assert (res.json()["is_deleted"], res.json()["sort_order"]) == (False, 1)
    assert [f["title"] for f in items(user, folder["id"])["files"]] == ["a"]
    assert other_user.client.post(f"/files/{a['id']}/undelete").status_code == 404


def test_undelete_file_with_same_title_is_409(user: TestUser) -> None:
    folder = mk_folder(user, "F")
    a = mk_file(user, "t", folder["id"])
    user.client.delete(f"/files/{a['id']}")
    mk_file(user, "t", folder["id"])
    res = user.client.post(f"/files/{a['id']}/undelete")
    assert (res.status_code, res.json()) == (409, {"detail": "同じタイトルがあります"})


def test_file_in_deleted_folder_is_flagged_and_uneditable(user: TestUser) -> None:
    a = mk_folder(user, "A")
    b = mk_folder(user, "B", a["id"])
    other = mk_folder(user, "Z")
    f = mk_file(user, "f", b["id"])
    user.client.delete(f"/folders/{a['id']}")
    listed = items(user, b["id"], include_deleted=True)["files"]
    assert [(x["is_deleted"], x["ancestor_deleted"]) for x in listed] == [(False, True)]
    assert user.client.patch(f"/files/{f['id']}", json={"title": "n"}).status_code == 409
    assert user.client.post(f"/files/{f['id']}/move", json={"new_folder_id": other["id"]}).status_code == 409
    # 上位を削除解除すると、元に戻る
    user.client.post(f"/folders/{a['id']}/undelete")
    assert [x["title"] for x in items(user, b["id"])["files"]] == ["f"]
    assert user.client.patch(f"/files/{f['id']}", json={"title": "n"}).status_code == 200


def test_file_endpoints_require_login() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    assert client.post("/files", json={"folder_id": 1, "title": "x"}).status_code == 401
    assert client.get("/files/1").status_code == 401
    assert client.delete("/files/1").status_code == 401
