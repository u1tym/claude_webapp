from __future__ import annotations

import base64
import dataclasses

import pytest

from app.config import load_config

from conftest import TestUser, mk_file, mk_folder, mk_part, sql_all

PDF1 = b"%PDF-1.4\n" + b"one" * 5
PDF2 = b"%PDF-1.7\n" + b"two" * 7
PNG = b"\x89PNG\r\n\x1a\n" + b"png" * 4


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


@pytest.fixture()
def file_id(user: TestUser) -> int:
    return mk_file(user, "f", mk_folder(user, "F")["id"])["id"]


def patch(user: TestUser, part_id: int, **body):
    return user.client.patch(f"/parts/{part_id}", json=body)


def test_create_pdf_part_and_view_inline(user: TestUser, file_id: int) -> None:
    part = mk_part(user, file_id, "pdf", b64(PDF1), filename="資料.pdf")
    assert (part["type"], part["data"], part["byte_size"], part["filename"]) == ("pdf", "", len(PDF1), "資料.pdf")
    assert part["revisions"] == []
    res = user.client.get(f"/parts/{part['id']}/content")
    assert res.status_code == 200 and res.content == PDF1
    assert res.headers["content-type"] == "application/pdf"
    assert res.headers["content-disposition"].startswith("inline;")
    assert "filename*=UTF-8''" in res.headers["content-disposition"]
    down = user.client.get(f"/parts/{part['id']}/content", params={"download": "true"})
    assert down.content == PDF1 and down.headers["content-disposition"].startswith("attachment;")


@pytest.mark.parametrize(
    ("body", "status", "detail"),
    [
        ({"data": b64(PNG), "filename": "a.pdf"}, 400, "PDF の形式が正しくありません"),
        ({"data": b64(b"not pdf"), "filename": "a.pdf"}, 400, "PDF の形式が正しくありません"),
        ({"data": "***", "filename": "a.pdf"}, 400, "ファイルの内容が正しくありません"),
        ({"data": b64(PDF1), "filename": "  "}, 400, "ファイル名を入力してください"),
    ],
)
def test_pdf_rejections(user: TestUser, file_id: int, body: dict, status: int, detail: str) -> None:
    res = user.client.post(f"/files/{file_id}/parts", json={"type": "pdf", **body})
    assert (res.status_code, res.json()["detail"]) == (status, detail)


def test_pdf_over_the_size_limit_is_413(user: TestUser, file_id: int, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.part_service as part_service

    cfg = dataclasses.replace(load_config(), part_max_bytes=16)
    monkeypatch.setattr(part_service, "load_config", lambda: cfg)
    res = user.client.post(f"/files/{file_id}/parts", json={"type": "pdf", "data": b64(PDF1), "filename": "a.pdf"})
    assert res.status_code == 413


def test_replacing_pdf_keeps_a_revision_that_can_be_downloaded(user: TestUser, file_id: int) -> None:
    part = mk_part(user, file_id, "pdf", b64(PDF1), filename="a.pdf")
    body = patch(user, part["id"], data=b64(PDF2)).json()
    assert [(r["revision_number"], r["type"], r["filename"], r["byte_size"]) for r in body["revisions"]] == [(1, "pdf", "a.pdf", len(PDF1))]
    assert user.client.get(f"/parts/{part['id']}/content").content == PDF2
    res = user.client.get(f"/part-revisions/{body['revisions'][0]['id']}/content")
    assert (res.content, res.headers["content-type"]) == (PDF1, "application/pdf")
    assert res.headers["content-disposition"].startswith("attachment;")


def test_type_change_between_binary_and_pdf_checks_the_content(user: TestUser, file_id: int) -> None:
    ok = mk_part(user, file_id, "binary", b64(PDF1), filename="a.bin")
    assert patch(user, ok["id"], type="pdf").status_code == 200  # 中身が PDF なら、データなしで変えられる
    bad = mk_part(user, file_id, "binary", b64(b"payload"), filename="b.bin")
    res = patch(user, bad["id"], type="pdf")
    assert (res.status_code, res.json()["detail"]) == (400, "PDF の形式が正しくありません")
    assert sql_all("SELECT ptype FROM note_management.parts WHERE id = %s", (bad["id"],))[0]["ptype"] == "binary"
    png = mk_part(user, file_id, "png", b64(PNG), filename="c.png")
    assert patch(user, png["id"], type="pdf").status_code == 400
    # PDF から画像へ: 中身が画像でないので断る
    res = patch(user, ok["id"], type="png")
    assert (res.status_code, res.json()["detail"]) == (400, "画像の形式が正しくありません")


def test_pdf_content_is_hidden_from_other_users(user: TestUser, other_user: TestUser, file_id: int) -> None:
    part = mk_part(user, file_id, "pdf", b64(PDF1), filename="a.pdf")
    assert other_user.client.get(f"/parts/{part['id']}/content").status_code == 404
    fetched = user.client.get(f"/files/{file_id}").json()["parts"][0]
    assert (fetched["type"], fetched["data"], fetched["byte_size"]) == ("pdf", "", len(PDF1))  # 一覧には中身を含めない
