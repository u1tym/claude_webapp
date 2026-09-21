from __future__ import annotations

import base64
import dataclasses
from urllib.parse import quote

import pytest

from app.config import load_config

from conftest import TestUser, mk_file, mk_folder, mk_part, sql_all, sql_one

PNG1 = b"\x89PNG\r\n\x1a\n" + b"one" * 5
PNG2 = b"\x89PNG\r\n\x1a\n" + b"two" * 7
PNG3 = b"\x89PNG\r\n\x1a\n" + b"three" * 3
JPEG = b"\xff\xd8\xff\xe0" + b"jpeg" * 4


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


@pytest.fixture()
def file_id(user: TestUser) -> int:
    return mk_file(user, "f", mk_folder(user, "F")["id"])["id"]


def patch(user: TestUser, part_id: int, **body):
    return user.client.patch(f"/parts/{part_id}", json=body)


def revisions(part_id: int) -> list[dict]:
    return sql_all(
        "SELECT id, revision_number, ptype, filename, data, byte_size FROM note_management.part_revisions "
        "WHERE part_id = %s ORDER BY revision_number",
        (part_id,),
    )


def test_replacing_content_keeps_the_previous_content_as_a_revision(user: TestUser, file_id: int) -> None:
    part = mk_part(user, file_id, "png", b64(PNG1), filename="a.png")
    assert part["revisions"] == []
    res = patch(user, part["id"], data=b64(PNG2))
    assert res.status_code == 200
    body = res.json()
    assert body["byte_size"] == len(PNG2)
    assert [(r["revision_number"], r["type"], r["filename"], r["byte_size"]) for r in body["revisions"]] == [(1, "png", "a.png", len(PNG1))]
    assert set(body["revisions"][0]) == {"id", "revision_number", "type", "filename", "byte_size", "created_at"}  # 中身は含めない
    assert body["revisions"][0]["created_at"]
    assert user.client.get(f"/parts/{part['id']}/content").content == PNG2  # 現在の内容は新しい方
    rows = revisions(part["id"])
    assert [(r["revision_number"], r["data"]) for r in rows] == [(1, b64(PNG1))]
    assert sql_one("SELECT user_id FROM note_management.part_revisions WHERE part_id = %s", (part["id"],))["user_id"] == user.id


def test_revision_numbers_increase_and_list_is_newest_first(user: TestUser, file_id: int) -> None:
    part = mk_part(user, file_id, "png", b64(PNG1), filename="a.png")
    patch(user, part["id"], data=b64(PNG2))
    body = patch(user, part["id"], data=b64(PNG3)).json()
    assert [r["revision_number"] for r in body["revisions"]] == [2, 1]
    detail = user.client.get(f"/files/{file_id}").json()["parts"][0]
    assert [r["revision_number"] for r in detail["revisions"]] == [2, 1]  # ファイルの取得でも同じ
    assert [r["data"] for r in revisions(part["id"])] == [b64(PNG1), b64(PNG2)]


def test_metadata_only_changes_do_not_add_a_revision(user: TestUser, file_id: int) -> None:
    part = mk_part(user, file_id, "png", b64(PNG1), filename="a.png", title="t")
    body = patch(user, part["id"], title="t2", image_scale=2, markers=[{"id": "m", "kind": "house", "x": 0, "y": 0, "text": ""}]).json()
    assert body["revisions"] == []
    assert patch(user, part["id"], data=b64(PNG1)).json()["revisions"] == []  # 同じ中身を送っても増えない
    assert revisions(part["id"]) == []


def test_changing_filename_or_type_adds_a_revision(user: TestUser, file_id: int) -> None:
    part = mk_part(user, file_id, "png", b64(PNG1), filename="a.png")
    body = patch(user, part["id"], filename="b.png").json()
    assert [(r["revision_number"], r["filename"]) for r in body["revisions"]] == [(1, "a.png")]
    body = patch(user, part["id"], type="binary").json()  # 中身は同じで、種別を変える
    assert [(r["revision_number"], r["type"], r["filename"]) for r in body["revisions"]] == [(2, "png", "b.png"), (1, "png", "a.png")]
    assert body["type"] == "binary"


def test_old_revisions_are_deleted_beyond_the_limit(user: TestUser, file_id: int, monkeypatch: pytest.MonkeyPatch) -> None:
    real = load_config()
    monkeypatch.setattr("app.services.part_service.load_config", lambda: dataclasses.replace(real, parts_max_revisions=2))
    part = mk_part(user, file_id, "binary", b64(b"v0"), filename="a.bin")
    for i in range(1, 5):
        body = patch(user, part["id"], data=b64(f"v{i}".encode())).json()
    # 5 回の中身のうち、現在（v4）を除く、新しい 2 世代（v3、v2）だけが残る。世代番号は増え続ける
    assert [r["revision_number"] for r in body["revisions"]] == [4, 3]
    assert [base64.b64decode(r["data"]) for r in revisions(part["id"])] == [b"v2", b"v3"]


def test_default_limit_is_three(user: TestUser, file_id: int) -> None:
    part = mk_part(user, file_id, "binary", b64(b"v0"), filename="a.bin")
    for i in range(1, 6):
        body = patch(user, part["id"], data=b64(f"v{i}".encode())).json()
    assert [r["revision_number"] for r in body["revisions"]] == [5, 4, 3]


def test_replacing_image_content_clears_markers_unless_given(user: TestUser, file_id: int) -> None:
    marker = {"id": "m", "kind": "house", "x": 0.1, "y": 0.1, "text": "x"}
    part = mk_part(user, file_id, "png", b64(PNG1), filename="a.png", markers=[marker], title="t", image_scale=2)
    body = patch(user, part["id"], data=b64(PNG2)).json()
    assert (body["markers"], body["title"], body["image_scale"]) == ([], "t", 2.0)  # マーカーは空。タイトル・倍率は維持
    body = patch(user, part["id"], data=b64(PNG3), markers=[marker]).json()
    assert body["markers"] == [marker]  # 要求にあれば、それを用いる


def test_image_type_change_checks_the_existing_content(user: TestUser, file_id: int) -> None:
    part = mk_part(user, file_id, "png", b64(PNG1), filename="a.png")
    res = patch(user, part["id"], type="jpeg")  # 中身は PNG のまま
    assert (res.status_code, res.json()) == (400, {"detail": "画像の形式が正しくありません"})
    res = patch(user, part["id"], type="jpeg", data=b64(JPEG))
    assert (res.status_code, res.json()["type"]) == (200, "jpeg")
    assert user.client.get(f"/parts/{part['id']}/content").headers["content-type"] == "image/jpeg"
    # バイナリから画像へ。中身が合えば、データを送らなくても変えられる
    binary = mk_part(user, file_id, "binary", b64(PNG1), filename="b.bin")
    assert patch(user, binary["id"], type="png").status_code == 200
    plain = mk_part(user, file_id, "binary", b64(b"not an image"), filename="c.bin")
    assert patch(user, plain["id"], type="png").status_code == 400
    assert sql_one("SELECT ptype FROM note_management.parts WHERE id = %s", (plain["id"],))["ptype"] == "binary"
    assert revisions(plain["id"]) == []  # 失敗したら、過去世代も増えない


def test_failed_replacement_leaves_everything_unchanged(user: TestUser, file_id: int) -> None:
    part = mk_part(user, file_id, "png", b64(PNG1), filename="a.png")
    assert patch(user, part["id"], data=b64(JPEG)).status_code == 400  # PNG に JPEG の中身
    assert patch(user, part["id"], data="***").status_code == 400
    assert revisions(part["id"]) == []
    assert user.client.get(f"/parts/{part['id']}/content").content == PNG1


def test_converting_binary_to_text_keeps_the_binary_as_a_revision(user: TestUser, file_id: int) -> None:
    part = mk_part(user, file_id, "binary", b64(b"payload"), filename="a.bin")
    res = patch(user, part["id"], type="text", data="now text")
    body = res.json()
    assert (res.status_code, body["type"], body["data"], body["filename"], body["byte_size"], body["revisions"]) == (200, "text", "now text", "", 0, [])
    assert [(r["ptype"], r["filename"], base64.b64decode(r["data"])) for r in revisions(part["id"])] == [("binary", "a.bin", b"payload")]
    assert user.client.get(f"/parts/{part['id']}/content").status_code == 404  # 画像・バイナリではなくなった


def test_revision_content_download(user: TestUser, other_user: TestUser, file_id: int) -> None:
    name = "旧 資料.png"
    part = mk_part(user, file_id, "png", b64(PNG1), filename=name)
    body = patch(user, part["id"], data=b64(PNG2)).json()
    rid = body["revisions"][0]["id"]
    res = user.client.get(f"/part-revisions/{rid}/content")
    assert res.status_code == 200
    assert res.content == PNG1
    assert res.headers["content-type"] == "image/png"
    disposition = res.headers["content-disposition"]
    assert disposition.startswith("attachment;")  # 過去世代は、常にダウンロード
    assert "filename*=UTF-8''" + quote(name, safe="") in disposition
    assert other_user.client.get(f"/part-revisions/{rid}/content").status_code == 404
    assert user.client.get("/part-revisions/999999999/content").status_code == 404
    # パーツが削除済みでも、取得できる
    user.client.delete(f"/parts/{part['id']}")
    assert user.client.get(f"/part-revisions/{rid}/content").content == PNG1


def test_revisions_of_other_users_are_not_visible(user: TestUser, other_user: TestUser, file_id: int) -> None:
    part = mk_part(user, file_id, "binary", b64(b"a"), filename="a.bin")
    patch(user, part["id"], data=b64(b"b"))
    assert other_user.client.get(f"/files/{file_id}").status_code == 404
    rid = revisions(part["id"])[0]["id"]
    assert other_user.client.get(f"/part-revisions/{rid}/content").status_code == 404


def test_revisions_survive_logical_delete_of_the_part(user: TestUser, file_id: int) -> None:
    part = mk_part(user, file_id, "binary", b64(b"a"), filename="a.bin")
    patch(user, part["id"], data=b64(b"b"))
    assert len(revisions(part["id"])) == 1
    user.client.delete(f"/parts/{part['id']}")  # 論理削除では、過去世代は残る
    assert len(revisions(part["id"])) == 1
