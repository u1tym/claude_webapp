"""契約の参照 API のテスト（REQ-004、REQ-005、REQ-007、REQ-013、REQ-014 / api-design.md GET）。"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from conftest import Owner, bearer, execute, insert_category, insert_contract, issue_key


def _setup(owner: Owner) -> dict[str, int]:
    """絞り込みの確認用の契約を、直接入れる。"""
    video = insert_category(owner, "動画配信")
    bank = insert_category(owner, "銀行", True)
    return {
        "video": video,
        "bank": bank,
        "netflix": insert_contract(
            owner, video, "Netflix", status="active", homepage="https://netflix.example",
            login_password=True, username="taro", password="pw1", registered_email="Me@Example.com", memo="家族で共有",
        ),
        "hulu": insert_contract(owner, video, "Hulu", status="paused", login_password=True, username="hanako"),
        "old": insert_contract(owner, video, "旧サービス", status="cancelled", memo="100%解約済み"),
        "card": insert_contract(owner, bank, "Aカード", has_contract=False, login_password=True, username="card-user", password="pw2"),
        "snake": insert_contract(owner, video, "a_b", status="active"),
        "ab": insert_contract(owner, video, "aXb", status="active"),
    }


def _list(c: TestClient, **params: Any) -> list[dict[str, Any]]:
    res = c.get("/contracts", params=params)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] == len(body["items"])
    return body["items"]


def _names(c: TestClient, **params: Any) -> list[str]:
    return [i["name"] for i in _list(c, **params)]


def test_list_all_in_name_order(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    owner = make_owner()
    ids = _setup(owner)
    c = make_client(owner)
    items = _list(c)
    assert [i["name"] for i in items] == ["a_b", "aXb", "Aカード", "Hulu", "Netflix", "旧サービス"]  # 名称の昇順（DB の照合順序に従う）。ステータスが解約のものも含む
    assert items[0]["category"] == {"id": ids["video"], "name": "動画配信", "is_financial": False}


def test_keyword_filter(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    owner = make_owner()
    _setup(owner)
    c = make_client(owner)
    assert _names(c, keyword="netflix") == ["Netflix"]  # 名称・大文字小文字を区別しない
    assert _names(c, keyword="NETFLIX.EXAMPLE") == ["Netflix"]  # ホームページ
    assert _names(c, keyword="me@example") == ["Netflix"]  # 登録メールアドレス
    assert _names(c, keyword="HANAKO") == ["Hulu"]  # ユーザ名
    assert _names(c, keyword="共有") == ["Netflix"]  # メモ
    assert _names(c, keyword="  Hulu  ") == ["Hulu"]  # 前後の空白は除く
    assert len(_names(c, keyword="")) == 6 and len(_names(c, keyword="   ")) == 6  # 空・空白のみは絞り込まない
    assert _names(c, keyword="該当なしの語") == []
    # パスワードは検索の対象外
    assert _names(c, keyword="pw1") == [] and _names(c, keyword="pw2") == []
    # LIKE の特殊文字は文字として扱う
    assert _names(c, keyword="%") == ["旧サービス"]
    assert _names(c, keyword="a_b") == ["a_b"]


def test_filters_and_combination(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    owner = make_owner()
    ids = _setup(owner)
    c = make_client(owner)
    assert _names(c, category_id=ids["bank"]) == ["Aカード"]
    assert _names(c, status="paused") == ["Hulu"]
    assert _names(c, status="cancelled") == ["旧サービス"]
    assert _names(c, has_contract="false") == ["Aカード"]
    assert len(_names(c, has_contract="true")) == 5
    assert _names(c, password_unset="true") == ["Hulu"]  # ユーザ名とパスワードを使い、パスワードが未設定
    assert len(_names(c, password_unset="false")) == 6  # false は絞り込まない
    # 組み合わせは、すべてに合うもの
    assert _names(c, category_id=ids["video"], status="active", keyword="net") == ["Netflix"]
    assert _names(c, category_id=ids["bank"], status="paused") == []
    assert _names(c, category_id=ids["bank"], status="active") == ["Aカード"]
    assert _names(c, has_contract="true", password_unset="true", keyword="hulu") == ["Hulu"]


def test_invalid_query_is_400(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    c = make_client(make_owner())
    for params in ({"status": "終了"}, {"has_contract": "maybe"}, {"password_unset": "x"}, {"category_id": "abc"}):
        assert c.get("/contracts", params=params).status_code == 400, params


def test_detail_and_password_never_in_representation(
    make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]
) -> None:
    owner = make_owner()
    ids = _setup(owner)
    c = make_client(owner)
    res = c.get(f"/contracts/{ids['netflix']}")
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "Netflix" and body["has_password"] is True and body["password_unset"] is False
    assert "pw1" not in json.dumps(body, ensure_ascii=False) and "password" not in body
    assert "pw1" not in json.dumps(c.get("/contracts").json(), ensure_ascii=False)
    assert "pw2" not in json.dumps(c.get("/accounts").json(), ensure_ascii=False)
    hulu = c.get(f"/contracts/{ids['hulu']}").json()
    assert hulu["has_password"] is False and hulu["password_unset"] is True


def test_password_endpoint(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    owner = make_owner()
    ids = _setup(owner)
    execute("UPDATE contract_management.contracts SET password = %s WHERE id = %s", ("  複数\n行  ", ids["old"]))
    c = make_client(owner)
    assert c.get(f"/contracts/{ids['netflix']}/password").json() == {"password": "pw1"}
    assert c.get(f"/contracts/{ids['old']}/password").json() == {"password": "  複数\n行  "}
    assert c.get(f"/contracts/{ids['hulu']}/password").json() == {"password": None}  # 未設定


def test_other_users_and_deleted_are_404(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    a = make_owner()
    b = make_owner()
    ids = _setup(a)
    cb = make_client(b)
    for path in (f"/contracts/{ids['netflix']}", f"/contracts/{ids['netflix']}/password"):
        assert cb.get(path).status_code == 404
    assert cb.get("/contracts").json() == {"total": 0, "items": []}
    assert cb.get("/accounts").json() == {"total": 0, "items": []}
    ca = make_client(a)
    execute("UPDATE contract_management.contracts SET is_deleted = true WHERE id = %s", (ids["netflix"],))
    assert ca.get(f"/contracts/{ids['netflix']}").status_code == 404
    assert ca.get(f"/contracts/{ids['netflix']}/password").status_code == 404
    assert "Netflix" not in _names(ca)
    assert ca.get("/contracts/999999999").status_code == 404
    assert ca.get("/contracts/abc").status_code == 400


def test_auth_required(client: TestClient) -> None:
    for path in ("/contracts", "/contracts/1", "/contracts/1/password", "/accounts"):
        assert client.get(path).status_code == 401, path


def test_api_key_scope(make_owner: Callable[..., Owner], client: TestClient) -> None:
    owner = make_owner()
    ids = _setup(owner)
    headers = bearer(issue_key(owner))
    # 一覧・詳細は許可
    listed = client.get("/contracts", headers=headers)
    assert listed.status_code == 200 and listed.json()["total"] == 6
    assert client.get(f"/contracts/{ids['netflix']}", headers=headers).status_code == 200
    # パスワードの取得とアカウント一覧は許可しない
    assert client.get(f"/contracts/{ids['netflix']}/password", headers=headers).status_code == 403
    assert client.get("/accounts", headers=headers).status_code == 403
    # 応答のどこにもパスワードの値がない
    assert "pw1" not in listed.text


def test_accounts(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    owner = make_owner()
    ids = _setup(owner)
    c = make_client(owner)
    res = c.get("/accounts")
    assert res.status_code == 200
    body = res.json()
    # ユーザ名またはパスワードを持つ契約だけ（契約を伴わない契約、ステータスが解約のものも対象）。名称の昇順
    assert [i["name"] for i in body["items"]] == ["Aカード", "Hulu", "Netflix"]
    assert body["total"] == 3
    netflix = body["items"][2]
    assert netflix == {
        "id": ids["netflix"], "name": "Netflix", "username": "taro",
        "homepage": "https://netflix.example", "has_password": True, "password_unset": False,
    }
    hulu = body["items"][1]
    assert hulu["has_password"] is False and hulu["password_unset"] is True
    # パスワードだけを持つ契約（ユーザ名なし）も対象
    only_pw = insert_contract(owner, ids["video"], "パスワードのみ", password="x")
    cancelled_with_name = insert_contract(owner, ids["video"], "解約済みアカウント", status="cancelled", username="u9")
    items = c.get("/accounts").json()["items"]
    by_id = {i["id"]: i for i in items}
    assert [i["name"] for i in items] == sorted(i["name"] for i in items)
    assert by_id[only_pw]["username"] is None and by_id[only_pw]["has_password"] is True
    assert cancelled_with_name in by_id
    # 削除済みは除く
    execute("UPDATE contract_management.contracts SET is_deleted = true WHERE id = %s", (ids["hulu"],))
    assert "Hulu" not in [i["name"] for i in c.get("/accounts").json()["items"]]


def test_accounts_keyword(make_owner: Callable[..., Owner], make_client: Callable[..., TestClient]) -> None:
    owner = make_owner()
    _setup(owner)
    c = make_client(owner)

    def names(keyword: str) -> list[str]:
        return [i["name"] for i in c.get("/accounts", params={"keyword": keyword}).json()["items"]]

    assert names("NETFLIX") == ["Netflix"]  # 名称
    assert names("hanako") == ["Hulu"]  # ユーザ名
    assert names("netflix.example") == ["Netflix"]  # ホームページ
    assert names("共有") == ["Netflix"]  # メモ
    assert names("me@example") == []  # 登録メールアドレスは対象外
    assert names("pw1") == []  # パスワードは対象外
    assert len(names("")) == 3 and len(names("  ")) == 3
