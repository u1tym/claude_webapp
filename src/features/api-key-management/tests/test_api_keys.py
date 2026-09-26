from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from conftest import AppUser, db_rows, log_text, login

KEY_PATTERN = re.compile(r"^wak_[A-Za-z0-9_-]{43}$")


def _future(days: int = 30) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).astimezone(
        timezone(timedelta(hours=9))
    ).isoformat()


def _expire_now(api_key_id: int) -> None:
    from app.db import get_conn

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE public.api_keys SET created_at = now() - interval '2 days', "
                "expires_at = now() - interval '1 day' WHERE id = %s",
                (api_key_id,),
            )


# ---- 発行 ----------------------------------------------------------------


def test_issue_without_expiry(client: TestClient, make_user: Callable[..., AppUser]) -> None:
    user = make_user()
    res = login(client, user).post("/api-keys", json={"name": "  家計簿連携  "})
    assert res.status_code == 201
    body = res.json()
    assert KEY_PATTERN.match(body["key"])
    assert body["key_prefix"] == body["key"][:12]
    assert body["name"] == "家計簿連携"
    assert body["status"] == "active"
    assert body["expires_at"] is None
    assert body["last_used_at"] is None
    assert body["revoked_at"] is None
    assert body["created_at"].endswith("Z")

    rows = db_rows("SELECT key_hash, key_prefix FROM public.api_keys WHERE id = %s", (body["id"],))
    assert rows[0]["key_hash"] == hashlib.sha256(body["key"].encode()).hexdigest()
    assert rows[0]["key_prefix"] == body["key_prefix"]
    stored = db_rows("SELECT * FROM public.api_keys WHERE id = %s", (body["id"],))[0]
    assert body["key"] not in [str(v) for v in stored.values()]


def test_issue_with_expiry(client: TestClient, make_user: Callable[..., AppUser]) -> None:
    user = make_user()
    expires = _future()
    res = login(client, user).post("/api-keys", json={"name": "期限付き", "expires_at": expires})
    assert res.status_code == 201
    body = res.json()
    assert body["expires_at"].endswith("Z")
    assert datetime.fromisoformat(body["expires_at"].replace("Z", "+00:00")) == datetime.fromisoformat(expires)


def test_issue_invalid_inputs(client: TestClient, make_user: Callable[..., AppUser]) -> None:
    user = make_user()
    login(client, user)
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    cases = [
        {},
        {"name": ""},
        {"name": "   "},
        {"name": "あ" * 101},
        {"name": 123},
        {"name": "x", "expires_at": past},
        {"name": "x", "expires_at": "2099-01-01T00:00:00"},
        {"name": "x", "expires_at": "not-a-date"},
    ]
    for payload in cases:
        res = client.post("/api-keys", json=payload)
        assert res.status_code == 400, payload
        assert res.json() == {"detail": "入力が不正です"}
    assert client.get("/api-keys").json()["items"] == []


def test_issue_name_max_length(client: TestClient, make_user: Callable[..., AppUser]) -> None:
    user = make_user()
    res = login(client, user).post("/api-keys", json={"name": "あ" * 100})
    assert res.status_code == 201


def test_issued_keys_are_unique(client: TestClient, make_user: Callable[..., AppUser]) -> None:
    user = make_user()
    login(client, user)
    keys = {client.post("/api-keys", json={"name": f"k{i}"}).json()["key"] for i in range(5)}
    assert len(keys) == 5


# ---- 一覧 ----------------------------------------------------------------


def test_list_own_keys_newest_first_with_status(
    client: TestClient, make_user: Callable[..., AppUser]
) -> None:
    user = make_user()
    other = make_user()
    login(client, other).post("/api-keys", json={"name": "他人のキー"})

    login(client, user)
    first = client.post("/api-keys", json={"name": "1本目"}).json()
    second = client.post("/api-keys", json={"name": "2本目"}).json()
    third = client.post("/api-keys", json={"name": "3本目"}).json()
    _expire_now(first["id"])
    client.post(f"/api-keys/{second['id']}/revoke")

    res = client.get("/api-keys")
    assert res.status_code == 200
    items = res.json()["items"]
    assert [item["name"] for item in items] == ["3本目", "2本目", "1本目"]
    assert {item["name"]: item["status"] for item in items} == {
        "1本目": "expired",
        "2本目": "revoked",
        "3本目": "active",
    }
    for item in items:
        assert "key" not in item
        assert "key_hash" not in item
        assert set(item) == {
            "id", "name", "key_prefix", "status", "created_at", "expires_at", "last_used_at", "revoked_at",
        }
    assert third["key"] not in res.text


# ---- 失効 ----------------------------------------------------------------


def test_revoke(client: TestClient, make_user: Callable[..., AppUser]) -> None:
    user = make_user()
    login(client, user)
    issued = client.post("/api-keys", json={"name": "失効対象"}).json()
    res = client.post(f"/api-keys/{issued['id']}/revoke")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "revoked"
    assert body["revoked_at"] is not None
    assert "key" not in body

    again = client.post(f"/api-keys/{issued['id']}/revoke")
    assert again.status_code == 409
    assert again.json() == {"detail": "既に失効しています"}
    assert len(client.get("/api-keys").json()["items"]) == 1


def test_revoke_expired_key(client: TestClient, make_user: Callable[..., AppUser]) -> None:
    user = make_user()
    login(client, user)
    issued = client.post("/api-keys", json={"name": "期限切れ"}).json()
    _expire_now(issued["id"])
    res = client.post(f"/api-keys/{issued['id']}/revoke")
    assert res.status_code == 200
    assert res.json()["status"] == "revoked"


def test_revoke_not_found_or_others(client: TestClient, make_user: Callable[..., AppUser]) -> None:
    owner = make_user()
    intruder = make_user()
    issued = login(client, owner).post("/api-keys", json={"name": "持ち主"}).json()

    login(client, intruder)
    res = client.post(f"/api-keys/{issued['id']}/revoke")
    assert res.status_code == 404
    assert res.json() == {"detail": "対象がありません"}
    assert client.post("/api-keys/999999999/revoke").status_code == 404
    assert client.post("/api-keys/abc/revoke").status_code == 400

    rows = db_rows("SELECT revoked_at FROM public.api_keys WHERE id = %s", (issued["id"],))
    assert rows[0]["revoked_at"] is None


# ---- ログ ----------------------------------------------------------------


def test_log_does_not_contain_key(
    client: TestClient, make_user: Callable[..., AppUser], log_dir: Path
) -> None:
    user = make_user()
    login(client, user)
    issued = client.post("/api-keys", json={"name": "ログ確認"}).json()
    client.get("/api-keys")
    client.post(f"/api-keys/{issued['id']}/revoke")
    client.post(f"/api-keys/{issued['id']}/revoke")

    text = log_text(log_dir)
    assert issued["key"] not in text
    assert hashlib.sha256(issued["key"].encode()).hexdigest() not in text
    assert user.session_id not in text
    assert f"API キー発行成功 username={user.username} id={issued['id']} prefix={issued['key_prefix']}" in text
    assert "API キー失効成功" in text
    assert "理由=失効済み" in text
    for line in text.splitlines():
        assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} (INF|WRN|ERR|DBG) ", line)
