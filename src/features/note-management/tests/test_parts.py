from __future__ import annotations

import base64
import dataclasses
import json
from urllib.parse import quote

import pytest

from app.config import load_config

from conftest import TestUser, mk_file, mk_folder, mk_part, sql_all, sql_one

JPEG = b"\xff\xd8\xff\xe0" + b"jpeg-body" * 3
PNG = b"\x89PNG\r\n\x1a\n" + b"png-body" * 3


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


@pytest.fixture()
def file_id(user: TestUser) -> int:
    return mk_file(user, "f", mk_folder(user, "F")["id"])["id"]


def post_part(user: TestUser, file_id: int, body: dict):
    return user.client.post(f"/files/{file_id}/parts", json=body)


def action(points, legs) -> str:
    return json.dumps({"points": points, "legs": legs}, ensure_ascii=False)


# ---- 追加: テキスト系 ------------------------------------------------------------


@pytest.mark.parametrize("ptype", ["text", "md", "tex", "url"])
def test_create_text_like_parts(user: TestUser, file_id: int, ptype: str) -> None:
    a = mk_part(user, file_id, ptype, "line1\nline2 ")
    b = mk_part(user, file_id, ptype, "")  # 本文が空でも登録できる
    assert (a["type"], a["data"], a["sort_order"], b["sort_order"], b["data"]) == (ptype, "line1\nline2 ", 1, 2, "")
    assert (a["byte_size"], a["filename"], a["title"], a["markers"], a["image_scale"]) == (0, "", "", [], 1.0)
    assert (a["checklist_id"], a["revisions"], a["is_deleted"]) == (None, [], False)
    row = sql_one("SELECT user_id, file_id, data FROM note_management.parts WHERE id = %s", (a["id"],))
    assert row == {"user_id": user.id, "file_id": file_id, "data": "line1\nline2 "}


def test_text_parts_ignore_image_fields(user: TestUser, file_id: int) -> None:
    part = mk_part(user, file_id, "text", "x", filename="a.png", title="t", markers=[{"id": "m"}], image_scale=9)
    assert (part["filename"], part["title"], part["markers"], part["image_scale"]) == ("", "", [], 1.0)


def test_create_rejections(user: TestUser, other_user: TestUser, file_id: int) -> None:
    for body in ({}, {"type": "table"}, {"type": "TEXT"}, {"type": 3}, {"data": "x"}):
        res = post_part(user, file_id, body)
        assert (res.status_code, res.json()) == (400, {"detail": "入力が不正です"}), body
    assert post_part(user, 999999999, {"type": "text"}).status_code == 404
    assert post_part(other_user, file_id, {"type": "text"}).status_code == 404
    assert sql_all("SELECT id FROM note_management.parts WHERE file_id = %s", (file_id,)) == []


def test_create_in_deleted_file_or_folder_is_409(user: TestUser) -> None:
    folder = mk_folder(user, "A")
    inner = mk_folder(user, "B", folder["id"])
    f1 = mk_file(user, "f1", folder["id"])
    f2 = mk_file(user, "f2", inner["id"])
    user.client.delete(f"/files/{f1['id']}")
    user.client.delete(f"/folders/{inner['id']}")
    for fid in (f1["id"], f2["id"]):
        res = post_part(user, fid, {"type": "text"})
        assert (res.status_code, res.json()) == (409, {"detail": "削除済みのため操作できません"})


# ---- 追加: 行動予定 --------------------------------------------------------------


def test_action_plan_is_normalized(user: TestUser, file_id: int) -> None:
    raw = action(
        [
            {"place": "東京駅  ", "time": "9:00 "},
            {"place": " 新宿", "arrive": "10:00", "depart": "10:30"},
            {"place": "", "time": ""},  # 末尾の空の地点は取り除く
            {"place": "  "},
        ],
        [{"memo": "山手線 ", "note": "快速\n2 号車 "}, {"memo": "x"}, {"memo": ""}],
    )
    part = mk_part(user, file_id, "action", raw)
    assert json.loads(part["data"]) == {
        "points": [{"place": "東京駅", "time": "9:00"}, {"place": " 新宿", "arrive": "10:00", "depart": "10:30"}],
        "legs": [{"memo": "山手線", "note": "快速\n2 号車"}],  # 空白は末尾だけ除く。先頭・途中は保つ
    }


def test_action_plan_keeps_leading_empty_point_and_single_point(user: TestUser, file_id: int) -> None:
    part = mk_part(user, file_id, "action", action([{"place": ""}, {"place": "渋谷", "time": "14:00"}], [{"memo": "徒歩"}]))
    assert json.loads(part["data"])["points"] == [{"place": ""}, {"place": "渋谷", "time": "14:00"}]  # 先頭が空でも保つ
    # 末尾の空の地点は、その手前の経由メモごと取り除く。残りがすべて空なら、保存できない
    res = post_part(user, file_id, {"type": "action", "data": action([{"place": ""}, {"place": ""}], [{"memo": "経由だけ"}])})
    assert (res.status_code, res.json()) == (400, {"detail": "行動予定の内容が正しくありません"})
    kept = mk_part(user, file_id, "action", action([{"place": ""}, {"place": ""}, {"place": "C"}], [{"memo": "経由だけ"}, {"memo": ""}]))
    assert json.loads(kept["data"])["legs"] == [{"memo": "経由だけ", "note": ""}, {"memo": "", "note": ""}]
    single = mk_part(user, file_id, "action", action([{"place": "A"}], []))
    assert json.loads(single["data"]) == {"points": [{"place": "A"}], "legs": []}


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "[]",
        json.dumps({}),
        json.dumps({"points": []}),
        json.dumps({"points": [{"place": "A"}, {"place": "B"}], "legs": []}),  # 経由メモの件数が違う
        json.dumps({"points": [{"place": "A"}], "legs": [{"memo": "x"}]}),
        json.dumps({"points": [{"place": "A", "arrive": "9:00"}], "legs": []}),  # 1 番目の地点に到着・出発は付けない
        json.dumps({"points": [{"place": "A"}, {"place": "B", "time": "1", "arrive": "2"}], "legs": [{}]}),
        json.dumps({"points": [{"place": "A"}, {"place": "B", "time": "1", "depart": "2"}], "legs": [{}]}),
        json.dumps({"points": [{"place": ""}, {"place": ""}], "legs": [{"memo": "", "note": ""}]}),  # すべて空
        json.dumps({"points": [{"place": "A", "zzz": 1}], "legs": []}),
        json.dumps({"points": [{"place": 1}], "legs": []}),
        json.dumps({"points": [{"place": "A"}, {"place": "B"}], "legs": [{"memo": 1}]}),
        json.dumps({"points": [{"place": "A"}, {"place": "B"}], "legs": [{"other": "x"}]}),
    ],
)
def test_action_plan_rejections(user: TestUser, file_id: int, raw: str) -> None:
    res = post_part(user, file_id, {"type": "action", "data": raw})
    assert (res.status_code, res.json()) == (400, {"detail": "行動予定の内容が正しくありません"})
    assert sql_all("SELECT id FROM note_management.parts WHERE file_id = %s", (file_id,)) == []


def test_action_without_data_is_rejected(user: TestUser, file_id: int) -> None:
    assert post_part(user, file_id, {"type": "action"}).status_code == 400


# ---- 追加: チェックリスト ---------------------------------------------------------


def test_create_checklist_part_makes_empty_checklist(user: TestUser, file_id: int) -> None:
    part = mk_part(user, file_id, "checklist", "ignored")
    assert part["data"] == ""
    assert isinstance(part["checklist_id"], int)
    row = sql_one("SELECT user_id, part_id, title FROM note_management.checklists WHERE id = %s", (part["checklist_id"],))
    assert row == {"user_id": user.id, "part_id": part["id"], "title": ""}
    assert sql_all("SELECT id FROM note_management.checklist_categories WHERE checklist_id = %s", (part["checklist_id"],)) == []


# ---- 追加: 画像・バイナリ ---------------------------------------------------------


def test_create_image_part_and_fetch_content(user: TestUser, file_id: int) -> None:
    markers = [{"id": "m1", "kind": "house", "x": 0.1, "y": 0.2, "text": "宿"}, {"id": "m2", "kind": "number", "x": 1, "y": 0, "text": "", "number": 1}]
    part = mk_part(user, file_id, "png", b64(PNG), filename=" map.png ", title="地図", markers=markers, image_scale=1.5)
    assert (part["data"], part["byte_size"], part["filename"], part["title"], part["image_scale"]) == ("", len(PNG), "map.png", "地図", 1.5)
    assert part["markers"] == markers
    row = sql_one("SELECT data, byte_size, markers, image_scale FROM note_management.parts WHERE id = %s", (part["id"],))
    assert row["data"] == b64(PNG)  # Base64 のまま持つ
    assert row["markers"] == markers
    # 中身は、別の取得で、元のバイト列が返る
    res = user.client.get(f"/parts/{part['id']}/content")
    assert res.status_code == 200
    assert res.content == PNG
    assert res.headers["content-type"] == "image/png"
    assert res.headers["content-disposition"].startswith("inline;")
    assert res.headers["cache-control"] == "private, no-cache"
    down = user.client.get(f"/parts/{part['id']}/content", params={"download": "true"})
    assert down.content == PNG and down.headers["content-disposition"].startswith("attachment;")


def test_image_defaults_and_jpeg(user: TestUser, file_id: int) -> None:
    part = mk_part(user, file_id, "jpeg", b64(JPEG), filename="a.jpg")
    assert (part["title"], part["markers"], part["image_scale"]) == ("", [], 1.0)
    res = user.client.get(f"/parts/{part['id']}/content")
    assert (res.content, res.headers["content-type"]) == (JPEG, "image/jpeg")


def test_binary_part_and_japanese_filename(user: TestUser, file_id: int) -> None:
    raw = bytes(range(256)) * 4
    name = '資料 "1".bin'
    part = mk_part(user, file_id, "binary", b64(raw), filename=name, title="ignored", markers=[{"id": "x"}], image_scale=3)
    assert (part["byte_size"], part["title"], part["markers"], part["image_scale"]) == (len(raw), "", [], 1.0)
    res = user.client.get(f"/parts/{part['id']}/content")
    assert res.content == raw
    assert res.headers["content-type"] == "application/octet-stream"
    disposition = res.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    assert "filename*=UTF-8''" + quote(name, safe="") in disposition
    ascii_part = disposition.split("filename=", 1)[1].split(";", 1)[0]  # 通常の filename は ASCII だけ。引用符を含めない
    assert ascii_part.startswith('"') and ascii_part.endswith('"') and '"' not in ascii_part[1:-1]
    assert ascii_part.isascii()


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        ({"type": "png", "data": b64(PNG)}, "ファイル名を入力してください"),
        ({"type": "png", "data": b64(PNG), "filename": "  "}, "ファイル名を入力してください"),
        ({"type": "binary", "data": b64(b"x")}, "ファイル名を入力してください"),
        ({"type": "png", "filename": "a.png"}, "ファイルの内容が正しくありません"),
        ({"type": "png", "filename": "a.png", "data": ""}, "ファイルの内容が正しくありません"),
        ({"type": "binary", "filename": "a", "data": "***not-base64***"}, "ファイルの内容が正しくありません"),
        ({"type": "jpeg", "filename": "a.jpg", "data": b64(PNG)}, "画像の形式が正しくありません"),
        ({"type": "png", "filename": "a.png", "data": b64(JPEG)}, "画像の形式が正しくありません"),
        ({"type": "png", "filename": "a.png", "data": b64(b"plain text")}, "画像の形式が正しくありません"),
    ],
)
def test_binary_and_image_rejections(user: TestUser, file_id: int, body: dict, detail: str) -> None:
    res = post_part(user, file_id, body)
    assert (res.status_code, res.json()) == (400, {"detail": detail})
    assert sql_all("SELECT id FROM note_management.parts WHERE file_id = %s", (file_id,)) == []


@pytest.mark.parametrize("scale", [0.24, 0.2, 4.01, 5, 0, -1])
def test_image_scale_out_of_range(user: TestUser, file_id: int, scale: float) -> None:
    res = post_part(user, file_id, {"type": "png", "data": b64(PNG), "filename": "a.png", "image_scale": scale})
    assert (res.status_code, res.json()) == (400, {"detail": "表示倍率は 25〜400% の範囲で指定してください"})


@pytest.mark.parametrize("scale", [0.25, 4.0, 1])
def test_image_scale_boundaries_are_accepted(user: TestUser, file_id: int, scale: float) -> None:
    part = mk_part(user, file_id, "png", b64(PNG), filename="a.png", image_scale=scale)
    assert part["image_scale"] == float(scale)


def good(i: int = 1, **extra) -> dict:
    return {"id": f"m{i}", "kind": "house", "x": 0.5, "y": 0.5, "text": "", **extra}


@pytest.mark.parametrize(
    "markers",
    [
        [good(x=-0.01)],
        [good(x=1.01)],
        [good(y=2)],
        [good(number=1)],  # 家マーカーに番号
        [{"id": "a", "kind": "number", "x": 0, "y": 0, "text": ""}],  # 番号マーカーに番号がない
        [{"id": "a", "kind": "number", "x": 0, "y": 0, "text": "", "number": 0}],
        [{"id": "a", "kind": "number", "x": 0, "y": 0, "text": "", "number": "1"}],
        [good(1), good(1)],  # id の重複
        [good(kind="star")],
        [good(id="")],
        [good(id="x" * 65)],
        [good(text=5)],
        ["not-an-object"],
    ],
)
def test_marker_rejections(user: TestUser, file_id: int, markers: list) -> None:
    res = post_part(user, file_id, {"type": "png", "data": b64(PNG), "filename": "a.png", "markers": markers})
    assert (res.status_code, res.json()) == (400, {"detail": "マーカーが正しくありません"})


def test_marker_count_limit(user: TestUser, file_id: int) -> None:
    body = {"type": "png", "data": b64(PNG), "filename": "a.png"}
    ok = post_part(user, file_id, {**body, "markers": [good(i) for i in range(100)]})
    assert ok.status_code == 201 and len(ok.json()["markers"]) == 100
    res = post_part(user, file_id, {**body, "markers": [good(i) for i in range(101)]})
    assert (res.status_code, res.json()) == (400, {"detail": "マーカーは 100 個までです"})


def test_size_limit_is_413(user: TestUser, file_id: int, monkeypatch: pytest.MonkeyPatch) -> None:
    real = load_config()
    monkeypatch.setattr("app.services.part_service.load_config", lambda: dataclasses.replace(real, part_max_bytes=64))
    body = {"type": "binary", "filename": "a.bin"}
    ok = post_part(user, file_id, {**body, "data": b64(b"x" * 64)})
    assert ok.status_code == 201
    res = post_part(user, file_id, {**body, "data": b64(b"x" * 65)})
    assert res.status_code == 413
    assert res.json() == {"detail": "ファイルは 0.0625 KB までです"}
    # 上限（既定 10 MB）の文言
    monkeypatch.setattr("app.services.part_service.load_config", lambda: dataclasses.replace(real, part_max_bytes=10485760))
    huge = post_part(user, file_id, {**body, "data": b64(b"x" * (10485760 + 1))})
    assert (huge.status_code, huge.json()) == (413, {"detail": "ファイルは 10 MB までです"})
    assert len(sql_all("SELECT id FROM note_management.parts WHERE file_id = %s", (file_id,))) == 1


# ---- ファイルの取得 -----------------------------------------------------------------


def test_file_detail_shape_and_order(user: TestUser) -> None:
    folder = mk_folder(user, "旅行")
    f = mk_file(user, "持ち物", folder["id"])
    t = mk_part(user, f["id"], "text", "hello")
    img = mk_part(user, f["id"], "png", b64(PNG), filename="a.png", title="図")
    cl = mk_part(user, f["id"], "checklist")
    res = user.client.get(f"/files/{f['id']}")
    assert res.status_code == 200
    body = res.json()
    assert (body["id"], body["title"], body["folder"], body["is_deleted"], body["ancestor_deleted"]) == (f["id"], "持ち物", {"id": folder["id"], "name": "旅行"}, False, False)
    assert [p["id"] for p in body["parts"]] == [t["id"], img["id"], cl["id"]]
    assert body["parts"][1]["data"] == ""  # 画像の中身は含めない
    assert body["parts"][1]["byte_size"] == len(PNG)
    assert body["parts"][2]["checklist_id"] == cl["checklist_id"]
    assert set(body["parts"][0]) == {"id", "sort_order", "type", "is_deleted", "data", "byte_size", "filename", "title", "markers", "image_scale", "checklist_id", "revisions"}


def test_file_detail_deleted_parts_and_deleted_file(user: TestUser, other_user: TestUser) -> None:
    folder = mk_folder(user, "A")
    f = mk_file(user, "f", folder["id"])
    a, b = mk_part(user, f["id"], "text", "a"), mk_part(user, f["id"], "text", "b")
    user.client.delete(f"/parts/{a['id']}")
    ids = lambda params: [p["id"] for p in user.client.get(f"/files/{f['id']}", params=params).json()["parts"]]  # noqa: E731
    assert ids({}) == [b["id"]]
    assert ids({"include_deleted_parts": "true"}) == [a["id"], b["id"]]
    flags = {p["id"]: p["is_deleted"] for p in user.client.get(f"/files/{f['id']}", params={"include_deleted_parts": "true"}).json()["parts"]}
    assert flags == {a["id"]: True, b["id"]: False}
    # 削除済みのファイルも取得できる
    user.client.delete(f"/files/{f['id']}")
    body = user.client.get(f"/files/{f['id']}").json()
    assert (body["is_deleted"], body["ancestor_deleted"], len(body["parts"])) == (True, False, 1)
    # 上位のフォルダが削除済み
    f2 = mk_file(user, "f2", mk_folder(user, "B", folder["id"])["id"])
    user.client.delete(f"/folders/{folder['id']}")
    body = user.client.get(f"/files/{f2['id']}").json()
    assert (body["is_deleted"], body["ancestor_deleted"]) == (False, True)
    assert other_user.client.get(f"/files/{f['id']}").status_code == 404
    assert user.client.get("/files/999999999").status_code == 404
    assert user.client.get(f"/files/{f['id']}", params={"include_deleted_parts": "maybe"}).status_code == 400


# ---- 削除・削除解除・入れ替え ---------------------------------------------------------


def test_delete_and_undelete_part(user: TestUser, other_user: TestUser, file_id: int) -> None:
    a = mk_part(user, file_id, "text", "a")
    b = mk_part(user, file_id, "text", "b")
    assert other_user.client.delete(f"/parts/{a['id']}").status_code == 404
    assert user.client.post(f"/parts/{a['id']}/undelete").status_code == 409
    res = user.client.delete(f"/parts/{a['id']}")
    assert (res.status_code, res.content) == (204, b"")
    assert sql_one("SELECT is_deleted FROM note_management.parts WHERE id = %s", (a["id"],))["is_deleted"] is True
    again = user.client.delete(f"/parts/{a['id']}")
    assert (again.status_code, again.json()) == (409, {"detail": "既に削除されています"})
    res = user.client.post(f"/parts/{a['id']}/undelete")
    assert res.status_code == 200
    assert (res.json()["is_deleted"], res.json()["sort_order"]) == (False, 1)  # 元の位置に戻る
    not_deleted = user.client.post(f"/parts/{b['id']}/undelete")
    assert (not_deleted.status_code, not_deleted.json()) == (409, {"detail": "削除されていません"})
    assert other_user.client.post(f"/parts/{a['id']}/undelete").status_code == 404
    assert user.client.delete("/parts/999999999").status_code == 404


def test_part_operations_in_deleted_file_are_409(user: TestUser, file_id: int) -> None:
    a, b = mk_part(user, file_id, "text", "a"), mk_part(user, file_id, "text", "b")
    user.client.delete(f"/parts/{b['id']}")
    user.client.delete(f"/files/{file_id}")
    detail = {"detail": "削除済みのため操作できません"}
    for res in (
        user.client.patch(f"/parts/{a['id']}", json={"data": "z"}),
        user.client.delete(f"/parts/{a['id']}"),
        user.client.post(f"/parts/{b['id']}/undelete"),
        user.client.post("/parts/swap-order", json={"part_id_1": a["id"], "part_id_2": b["id"]}),
    ):
        assert (res.status_code, res.json()) == (409, detail)
    assert sql_one("SELECT data FROM note_management.parts WHERE id = %s", (a["id"],))["data"] == "a"


def test_swap_parts(user: TestUser, other_user: TestUser, file_id: int) -> None:
    a, b, c = (mk_part(user, file_id, "text", t) for t in "abc")
    res = user.client.post("/parts/swap-order", json={"part_id_1": a["id"], "part_id_2": c["id"]})
    assert (res.status_code, res.content) == (204, b"")
    orders = {r["data"]: r["sort_order"] for r in sql_all("SELECT data, sort_order FROM note_management.parts WHERE file_id = %s", (file_id,))}
    assert orders == {"a": 3, "b": 2, "c": 1}
    assert [p["data"] for p in user.client.get(f"/files/{file_id}").json()["parts"]] == ["c", "b", "a"]

    other_file = mk_file(user, "g", mk_folder(user, "G")["id"])["id"]
    x = mk_part(user, other_file, "text", "x")
    theirs = mk_part(other_user, mk_file(other_user, "t", mk_folder(other_user, "T")["id"])["id"], "text")
    post = lambda p, q: user.client.post("/parts/swap-order", json={"part_id_1": p, "part_id_2": q})  # noqa: E731
    assert post(a["id"], a["id"]).status_code == 400
    res = post(a["id"], x["id"])
    assert (res.status_code, res.json()) == (400, {"detail": "同じ場所の項目ではありません"})
    assert post(a["id"], theirs["id"]).status_code == 404
    user.client.delete(f"/parts/{b['id']}")
    res = post(a["id"], b["id"])
    assert (res.status_code, res.json()) == (409, {"detail": "削除済みのため操作できません"})


# ---- 更新 -----------------------------------------------------------------------


def test_update_text_keeps_omitted_values(user: TestUser, file_id: int) -> None:
    part = mk_part(user, file_id, "md", "# title")
    res = user.client.patch(f"/parts/{part['id']}", json={"data": "# new"})
    assert (res.status_code, res.json()["data"], res.json()["type"]) == (200, "# new", "md")
    res = user.client.patch(f"/parts/{part['id']}", json={})  # 何も指定しない
    assert (res.status_code, res.json()["data"]) == (200, "# new")
    res = user.client.patch(f"/parts/{part['id']}", json={"data": ""})  # 空にもできる
    assert res.json()["data"] == ""


def test_update_type_within_text_group_keeps_data(user: TestUser, file_id: int) -> None:
    part = mk_part(user, file_id, "text", "body")
    res = user.client.patch(f"/parts/{part['id']}", json={"type": "tex"})
    assert (res.status_code, res.json()["type"], res.json()["data"]) == (200, "tex", "body")
    res = user.client.patch(f"/parts/{part['id']}", json={"type": "url", "data": "https://example.com"})
    assert (res.json()["type"], res.json()["data"]) == ("url", "https://example.com")


def test_update_across_groups_requires_data(user: TestUser, file_id: int) -> None:
    part = mk_part(user, file_id, "text", "body")
    for new_type, extra in (("action", {}), ("png", {"filename": "a.png"}), ("binary", {"filename": "a"})):
        res = user.client.patch(f"/parts/{part['id']}", json={"type": new_type, **extra})
        assert (res.status_code, res.json()) == (400, {"detail": "内容を指定してください"}), new_type
    assert sql_one("SELECT ptype, data FROM note_management.parts WHERE id = %s", (part["id"],)) == {"ptype": "text", "data": "body"}
    res = user.client.patch(f"/parts/{part['id']}", json={"type": "action", "data": action([{"place": "A "}], [])})
    assert (res.status_code, json.loads(res.json()["data"])) == (200, {"points": [{"place": "A"}], "legs": []})
    res = user.client.patch(f"/parts/{part['id']}", json={"type": "text"})  # action から text も、組をまたぐ
    assert res.status_code == 400
    res = user.client.patch(f"/parts/{part['id']}", json={"type": "text", "data": "back"})
    assert (res.status_code, res.json()["data"]) == (200, "back")


def test_update_to_or_from_checklist_is_409(user: TestUser, file_id: int) -> None:
    text = mk_part(user, file_id, "text", "x")
    cl = mk_part(user, file_id, "checklist")
    msg = {"detail": "チェックリストの種別は変更できません"}
    res = user.client.patch(f"/parts/{text['id']}", json={"type": "checklist", "data": ""})
    assert (res.status_code, res.json()) == (409, msg)
    res = user.client.patch(f"/parts/{cl['id']}", json={"type": "text", "data": "x"})
    assert (res.status_code, res.json()) == (409, msg)
    assert sql_one("SELECT ptype FROM note_management.parts WHERE id = %s", (cl["id"],))["ptype"] == "checklist"
    # チェックリストのパーツに、種別の変更のない更新をしても、何も変わらない
    res = user.client.patch(f"/parts/{cl['id']}", json={"data": "junk"})
    assert (res.status_code, res.json()["data"], res.json()["checklist_id"]) == (200, "", cl["checklist_id"])


def test_update_image_fields(user: TestUser, file_id: int) -> None:
    part = mk_part(user, file_id, "png", b64(PNG), filename="a.png", title="t1", image_scale=2, markers=[good()])
    res = user.client.patch(f"/parts/{part['id']}", json={"title": "t2"})
    body = res.json()
    assert (res.status_code, body["title"], body["image_scale"], body["markers"], body["filename"]) == (200, "t2", 2.0, [good()], "a.png")
    body = user.client.patch(f"/parts/{part['id']}", json={"image_scale": 0.5, "markers": []}).json()
    assert (body["title"], body["image_scale"], body["markers"]) == ("t2", 0.5, [])
    assert user.client.patch(f"/parts/{part['id']}", json={"image_scale": 9}).status_code == 400
    assert user.client.patch(f"/parts/{part['id']}", json={"markers": [good(1), good(1)]}).status_code == 400
    assert user.client.patch(f"/parts/{part['id']}", json={"filename": " "}).status_code == 400
    assert user.client.get(f"/parts/{part['id']}/content").content == PNG  # 中身は変わらない


def test_update_to_non_image_resets_image_fields(user: TestUser, file_id: int) -> None:
    part = mk_part(user, file_id, "png", b64(PNG), filename="a.png", title="t", image_scale=2, markers=[good()])
    body = user.client.patch(f"/parts/{part['id']}", json={"type": "binary"}).json()  # 中身は引き継ぐ
    assert (body["type"], body["title"], body["image_scale"], body["markers"], body["byte_size"]) == ("binary", "", 1.0, [], len(PNG))
    row = sql_one("SELECT title, image_scale, markers FROM note_management.parts WHERE id = %s", (part["id"],))
    assert (row["title"], row["image_scale"], row["markers"]) == ("", 1.0, [])
    assert user.client.get(f"/parts/{part['id']}/content").content == PNG


def test_update_rejections(user: TestUser, other_user: TestUser, file_id: int) -> None:
    part = mk_part(user, file_id, "text", "x")
    assert other_user.client.patch(f"/parts/{part['id']}", json={"data": "z"}).status_code == 404
    assert user.client.patch("/parts/999999999", json={"data": "z"}).status_code == 404
    for body in ({"type": "table"}, {"data": 5}, {"image_scale": "big"}):
        assert user.client.patch(f"/parts/{part['id']}", json=body).status_code == 400, body
    user.client.delete(f"/parts/{part['id']}")
    res = user.client.patch(f"/parts/{part['id']}", json={"data": "z"})
    assert (res.status_code, res.json()) == (409, {"detail": "削除済みのため操作できません"})


# ---- 中身の取得 -----------------------------------------------------------------


def test_content_rejections(user: TestUser, other_user: TestUser, file_id: int) -> None:
    text = mk_part(user, file_id, "text", "x")
    img = mk_part(user, file_id, "png", b64(PNG), filename="a.png")
    assert user.client.get(f"/parts/{text['id']}/content").status_code == 404  # 画像・バイナリではない
    assert other_user.client.get(f"/parts/{img['id']}/content").status_code == 404
    assert user.client.get("/parts/999999999/content").status_code == 404
    # 削除済みのパーツ・ファイルのものも取得できる
    user.client.delete(f"/parts/{img['id']}")
    user.client.delete(f"/files/{file_id}")
    assert user.client.get(f"/parts/{img['id']}/content").content == PNG


def test_part_endpoints_require_login(file_id: int) -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    assert client.post(f"/files/{file_id}/parts", json={"type": "text"}).status_code == 401
    assert client.patch("/parts/1", json={}).status_code == 401
    assert client.get("/parts/1/content").status_code == 401
    assert client.get("/part-revisions/1/content").status_code == 401
