"""操作の記録（REQ-014）。入力・判断結果・失敗理由が残り、本文・中身・秘密は残らない。"""

from __future__ import annotations

import base64
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

from conftest import TestUser, log_text, mk_file, mk_folder, mk_part

SECRET_TEXT = "SECRET-BODY-TEXT-12345"
PNG = b"\x89PNG\r\n\x1a\n" + b"UNIQUEPNGBYTES" * 4


def test_operations_and_results_are_logged(user: TestUser, log_dir: Path) -> None:
    folder = mk_folder(user, "ログ用フォルダ")
    file_ = mk_file(user, "ログ用ファイル", folder["id"])
    user.client.get("/items", params={"folder_id": folder["id"]})
    user.client.get(f"/files/{file_['id']}")
    text = log_text(log_dir)
    for expected in (
        "フォルダ作成要求", "フォルダ作成成功", "ファイル作成要求", "ファイル作成成功", "一覧取得要求", "一覧取得成功", "ファイル取得要求", "ファイル取得成功",
        "ログ用フォルダ", "ログ用ファイル",
    ):
        assert expected in text, expected
    assert f"user_id={user.id}" in text
    assert " INF " in text


def test_failures_log_the_internal_reason_but_not_the_response(user: TestUser, log_dir: Path) -> None:
    mk_folder(user, "dup")
    res = user.client.post("/folders", json={"parent_id": None, "name": "dup"})
    assert res.json() == {"detail": "同じ名前があります"}
    assert "理由=フォルダ名重複" in log_text(log_dir)
    res = user.client.get("/files/999999999")
    assert res.status_code == 404
    text = log_text(log_dir)
    assert "WRN" in text and "ファイルなし" in text
    user.client.post("/folders", json={"parent_id": None, "name": " "})
    assert "入力不正" in log_text(log_dir)


def test_part_content_and_secrets_are_never_logged(user: TestUser, log_dir: Path) -> None:
    file_ = mk_file(user, "f", mk_folder(user, "F")["id"])
    text_part = mk_part(user, file_["id"], "text", SECRET_TEXT)
    b64 = base64.b64encode(PNG).decode()
    img = mk_part(user, file_["id"], "png", b64, filename="a.png", title="TITLE-XYZ")
    user.client.patch(f"/parts/{text_part['id']}", json={"data": SECRET_TEXT + "-2"})
    user.client.patch(f"/parts/{img['id']}", json={"data": b64[:-8] + "AAAAAAAA"})  # 失敗（形式は合うが Base64 の末尾を変える）でも成功でも、中身は出ない
    user.client.get(f"/parts/{img['id']}/content")
    user.client.get(f"/files/{file_['id']}")
    cl = mk_part(user, file_["id"], "checklist")
    user.client.post(f"/checklists/{cl['checklist_id']}/items", json={"title": "ITEM-TITLE-SECRET"})
    text = log_text(log_dir)
    assert "パーツ追加成功" in text and "type=png" in text and f"byte_size={len(PNG)}" in text  # 識別子・種別・大きさは出る
    assert "パーツ更新成功" in text
    for secret in (SECRET_TEXT, b64, b64[:40], base64.b64encode(b"UNIQUEPNGBYTES").decode()):
        assert secret not in text, secret[:20]
    session_id = user.client.cookies.get("session_id")
    assert session_id and session_id not in text
    assert "session_id" not in text


def test_unauthenticated_requests_are_logged_without_cookie_values(log_dir: Path) -> None:
    client = TestClient(app)
    client.cookies.set("session_id", "00000000-0000-0000-0000-000000000001")
    assert client.get("/items").status_code == 401
    text = log_text(log_dir)
    assert "認証失敗" in text
    assert "00000000-0000-0000-0000-000000000001" not in text
