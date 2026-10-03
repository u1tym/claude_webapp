"""ログのテスト（REQ-011 / design.md ログ）。入力・判断結果・失敗理由が出て、機微な値が出ないこと。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import psycopg2
import pytest
from fastapi.testclient import TestClient

from app.logger import LOG_FILE
from conftest import Owner, bearer, issue_key

SECRETS = ("S3cret-Pass", "secret-user-x", "secret-mail@example.com", "2fa-secret@example.com", "090-9999-0000")


def _log(log_dir: Path) -> str:
    path = log_dir / LOG_FILE
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _full_contract(name: str = "ログ確認") -> dict[str, object]:
    return {
        "name": name,
        "login_methods": ["password", "2fa_mail", "2fa_tel"],
        "twofa_mail_address": "2fa-secret@example.com",
        "twofa_tel_number": "090-9999-0000",
        "username": "secret-user-x",
        "password": "S3cret-Pass",
        "registered_email": "secret-mail@example.com",
    }


def test_operations_are_logged_without_secrets(
    make_owner: Callable[..., Owner], make_client: Callable[..., TestClient], log_dir: Path
) -> None:
    owner = make_owner()
    c = make_client(owner)
    cat = c.post("/categories", json={"name": "ログ区分"}).json()
    created = c.post("/contracts", json=_full_contract()).json()
    cid = created["id"]
    c.get("/contracts", params={"keyword": "ログ"})
    c.get("/accounts", params={"keyword": "ログ確認"})
    c.get(f"/contracts/{cid}")
    c.get(f"/contracts/{cid}/password")
    c.patch(f"/contracts/{cid}", json={**_full_contract("更新後"), "password": "S3cret-Pass"})
    c.put("/cancellation-plan", json={"contract_ids": [cid]})
    c.get("/cancellation-plan")
    c.delete(f"/contracts/{cid}")
    c.delete(f"/categories/{cat['id']}")
    text = _log(log_dir)
    # 入力・判断結果が残る
    for expected in (
        "区分追加要求", "区分追加成功", "契約登録要求", "契約登録入力", "契約登録成功", "契約一覧要求", "契約一覧成功",
        "アカウント一覧要求", "アカウント一覧成功", "契約詳細要求", "契約詳細成功", "パスワード取得要求",
        "パスワード取得成功", "契約更新要求", "契約更新成功", "解約順保存要求", "解約順保存成功", "解約順取得成功",
        "契約削除要求", "契約削除成功", "区分削除成功",
    ):
        assert expected in text, expected
    assert "name='ログ確認'" in text and f"id={cid}" in text and f"user_id={owner.id}" in text
    # 行の形式: タイムスタンプ、区分、メッセージ
    for line in text.strip().splitlines():
        parts = line.split(" ", 3)
        assert len(parts) == 4 and parts[2] in ("INF", "WRN", "ERR", "DBG"), line
    # 機微な値はどこにも出ない
    for secret in SECRETS:
        assert secret not in text, secret
    assert owner.session_id not in text


def test_failures_are_logged_with_reasons(
    make_owner: Callable[..., Owner], make_client: Callable[..., TestClient], client: TestClient, log_dir: Path
) -> None:
    owner = make_owner()
    other = make_owner()
    c = make_client(owner)
    assert c.post("/contracts", json={"name": "", "password": "S3cret-Pass"}).status_code == 400
    assert c.post("/contracts", json={"name": "x", "password": "S3cret-Pass", "bogus": 1}).status_code == 400
    assert c.patch("/contracts/999999999", json={"name": "x"}).status_code == 404
    assert c.get("/contracts/999999999/password").status_code == 404
    assert c.post("/categories", json={"name": "その他"}).status_code == 409
    assert client.get("/contracts").status_code == 401
    assert make_client(other).get("/settings").status_code in (200, 500)
    unassigned = make_owner(assigned=False)
    assert make_client(unassigned).get("/contracts").status_code == 403
    headers = bearer(issue_key(owner))
    assert client.post("/contracts", json={"name": "x", "password": "S3cret-Pass"}, headers=headers).status_code == 400
    assert client.delete("/contracts/1", headers=headers).status_code == 403
    assert client.get("/contracts", headers={"Authorization": "Bearer wak_invalid-key-value"}).status_code == 401
    text = _log(log_dir)
    for expected in (
        "入力不正", "対象なし", "競合", "認証失敗 理由=未ログイン", "認可失敗", "API キーでは許可しない操作",
        "API キー認証失敗", "API キー認証成功",
    ):
        assert expected in text, expected
    assert "WRN" in text
    # API キーの識別用の先頭部分と持ち主のユーザ名は出るが、キー全体は出ない
    assert owner.username in text and "wak_invalid-" in text and "wak_invalid-key-value" not in text
    for secret in SECRETS:
        assert secret not in text, secret


def test_unexpected_failure_logs_only_first_line_of_db_error(
    make_owner: Callable[..., Owner], monkeypatch: pytest.MonkeyPatch, log_dir: Path
) -> None:
    from app.main import app
    from app.services import contract_service

    def boom(*_args: object, **_kwargs: object) -> None:
        raise psycopg2.DataError("first line of the error\nDETAIL:  Failing row contains (S3cret-Pass, secret-user-x)")

    monkeypatch.setattr(contract_service, "list_accounts", boom)
    owner = make_owner()
    c = TestClient(app, raise_server_exceptions=False)
    c.cookies.set("session_id", owner.session_id)
    res = c.get("/accounts")
    assert res.status_code == 500 and res.json() == {"detail": "サーバエラーです"}
    text = _log(log_dir)
    assert "ERR" in text and "想定外の失敗" in text and "type=DataError" in text and "first line of the error" in text
    assert "S3cret-Pass" not in text and "secret-user-x" not in text and "Failing row" not in text


def test_validation_reason_has_location_and_type_but_not_value(
    make_owner: Callable[..., Owner], make_client: Callable[..., TestClient], log_dir: Path
) -> None:
    c = make_client(make_owner())
    assert c.post("/contracts", json={"name": "x", "fee_amount": "S3cret-Pass"}).status_code == 400
    text = _log(log_dir)
    assert "入力不正 POST /contracts" in text and "fee_amount" in text
    assert "S3cret-Pass" not in text
