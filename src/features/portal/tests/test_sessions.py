"""同じユーザの複数端末での同時ログイン（タスク 13）のテスト。

端末ごとに TestClient を作る（Cookie の入れ物が別になる）。期限の操作は、開発用 DB の `public.sessions` を直接更新する。
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import load_config
from app.db import get_conn
from app.main import app
from app.repos import insert_assignment, insert_feature, insert_user, logical_delete_user
from app.security import hash_password
from png_bytes import PNG_1X1

CREATED_USER_IDS: list[int] = []


def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


@pytest.fixture(autouse=True)
def cleanup_sessions() -> Iterator[None]:
    """このテストで作ったユーザのセッション行を、終わりに片付ける（開発用 DB に積み残さない）。"""
    yield
    if CREATED_USER_IDS:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM public.sessions WHERE user_id = ANY(%s)", (list(CREATED_USER_IDS),))
        CREATED_USER_IDS.clear()


def _make_user(with_menu: bool = True) -> tuple[str, int]:
    username = _unique("multi")
    user = insert_user(username, hash_password("secret"))
    CREATED_USER_IDS.append(user.id)
    if with_menu:
        feature_id = _unique("feat")
        insert_feature(feature_id, "デモ", "http://example.local/demo", PNG_1X1, "image/png")
        insert_assignment(user.id, feature_id, 1)
    return username, user.id


def _login(username: str, password: str = "secret") -> TestClient:
    """新しい端末（Cookie の入れ物が別のクライアント）で、ログインする。"""
    client = TestClient(app)
    res = client.post("/auth/login", json={"username": username, "password": password})
    assert res.status_code == 204, res.text
    return client


def _session_id(client: TestClient) -> str:
    value = client.cookies.get("session_id")
    assert value
    return value


def _rows(user_id: int) -> dict[str, datetime]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, expires_at FROM public.sessions WHERE user_id = %s", (user_id,))
            return {str(row["id"]): row["expires_at"] for row in cur.fetchall()}


def _set_expiry(session_id: str, expires_at: datetime) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE public.sessions SET expires_at = %s WHERE id = %s", (expires_at, session_id))


def _insert_expired(user_id: int) -> str:
    session_id = str(uuid4())
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO public.sessions (id, user_id, expires_at) VALUES (%s, %s, now() - interval '1 hour')",
                (session_id, user_id),
            )
    return session_id


def _alive(client: TestClient) -> bool:
    return client.get("/auth/session").status_code == 200


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---- 同時ログイン ----


@pytest.mark.parametrize("devices", [2, 3])
def test_同じユーザが続けてログインしても_先のセッションが使える(devices: int) -> None:
    username, _ = _make_user()
    clients = [_login(username) for _ in range(devices)]

    for client in clients:
        assert client.get("/auth/session").json() == {"username": username}
        menu = client.get("/menu")
        assert menu.status_code == 200
        assert len(menu.json()["items"]) == 1
    assert len({_session_id(c) for c in clients}) == devices  # 端末ごとに、別のセッション


def test_同時にログインできる数に上限は無い() -> None:
    username, user_id = _make_user()
    clients = [_login(username) for _ in range(10)]
    assert all(_alive(c) for c in clients)
    assert len(_rows(user_id)) == 10


def test_あとからのログインは_他のユーザのセッションを変えない() -> None:
    first_name, first_id = _make_user()
    second_name, second_id = _make_user()
    first = _login(first_name)
    before = _rows(first_id)

    second = _login(second_name)
    _login(second_name)

    assert _rows(first_id) == before
    assert _alive(first) and _alive(second)
    assert len(_rows(second_id)) == 2


def test_失敗したログインは_既存のセッションを消さない() -> None:
    username, user_id = _make_user()
    device = _login(username)
    before = _rows(user_id)

    wrong = TestClient(app).post("/auth/login", json={"username": username, "password": "wrong"})
    assert wrong.status_code == 401
    unknown = TestClient(app).post("/auth/login", json={"username": "no-such-user-xyz", "password": "secret"})
    assert unknown.status_code == 401

    assert _rows(user_id) == before
    assert _alive(device)


# ---- ログアウト ----


def test_一方の端末でログアウトしても_もう一方は有効のまま() -> None:
    username, user_id = _make_user()
    pc = _login(username)
    phone = _login(username)
    phone_id = _session_id(phone)

    assert pc.post("/auth/logout").status_code == 204

    assert pc.get("/auth/session").status_code == 401  # ログアウトした端末は、未ログイン
    assert phone.get("/auth/session").status_code == 200  # もう一方は、続く
    assert phone.get("/menu").status_code == 200
    assert list(_rows(user_id)) == [phone_id]  # 消えたのは、ログアウトした 1 行だけ


def test_ログアウトした端末で_もう一度ログインできる() -> None:
    username, _ = _make_user()
    other = _login(username)
    device = _login(username)
    device.post("/auth/logout")
    device_again = _login(username)
    assert _alive(device_again) and _alive(other)


# ---- 論理削除 ----


def test_論理削除で_そのユーザの複数のセッションがすべて無効になる() -> None:
    username, user_id = _make_user()
    other_name, other_id = _make_user()
    devices = [_login(username) for _ in range(3)]
    bystander = _login(other_name)

    logical_delete_user(user_id)

    for client in devices:
        assert client.get("/auth/session").status_code == 401
        assert client.get("/menu").status_code == 401
    assert _rows(user_id) == {}
    assert _alive(bystander)  # 他のユーザは、変わらない
    assert len(_rows(other_id)) == 1


def test_論理削除したユーザは_再ログインできない() -> None:
    username, user_id = _make_user()
    _login(username)
    logical_delete_user(user_id)
    res = TestClient(app).post("/auth/login", json={"username": username, "password": "secret"})
    assert res.status_code == 401


# ---- 期限 ----


def test_期限切れのセッションは未ログインとして扱われる() -> None:
    username, _ = _make_user()
    expired = _login(username)
    alive = _login(username)
    _set_expiry(_session_id(expired), _now() - timedelta(minutes=1))

    assert expired.get("/auth/session").status_code == 401
    assert expired.get("/menu").status_code == 401
    assert alive.get("/auth/session").status_code == 200


def test_ログインの機会に_そのユーザの期限切れの行だけが削除される() -> None:
    username, user_id = _make_user()
    other_name, other_id = _make_user()
    device_a = _login(username)  # 期限内（残る）
    other_alive = _login(other_name)
    stale = _insert_expired(user_id)  # 同じユーザの期限切れ（消える）
    other_stale = _insert_expired(other_id)  # 他のユーザの期限切れ（このユーザのログインでは、変わらない）
    assert stale in _rows(user_id)

    device_b = _login(username)

    rows = _rows(user_id)
    assert stale not in rows  # 期限切れだけが消えた
    assert _session_id(device_a) in rows  # 期限内の他の端末は、残る
    assert _session_id(device_b) in rows
    assert len(rows) == 2
    assert other_stale in _rows(other_id)  # 他のユーザの期限切れの行は、変わらない
    assert _alive(device_a) and _alive(device_b) and _alive(other_alive)


def test_期限切れの行は_ログインを重ねても溜まらない() -> None:
    username, user_id = _make_user()
    for _ in range(5):
        _insert_expired(user_id)
    assert len(_rows(user_id)) == 5
    _login(username)
    assert len(_rows(user_id)) == 1


def test_有効期限の延長は_端末ごとに独立している() -> None:
    username, _ = _make_user()
    cfg = load_config()
    a = _login(username)
    b = _login(username)
    soon = _now() + timedelta(minutes=1)
    _set_expiry(_session_id(a), soon)
    _set_expiry(_session_id(b), soon)

    assert _alive(a)  # a だけを使う

    rows = _rows_by_client(a, b)
    assert rows["a"] > _now() + timedelta(minutes=cfg.session_timeout_minutes - 1)  # a は、延びた
    assert abs((rows["b"] - soon).total_seconds()) < 1  # b は、変わらない

    assert _alive(b)  # b を使うと、b が延びる
    assert _rows_by_client(a, b)["b"] > _now() + timedelta(minutes=cfg.session_timeout_minutes - 1)


def _rows_by_client(a: TestClient, b: TestClient) -> dict[str, datetime]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, expires_at FROM public.sessions WHERE id = ANY(%s::uuid[])",
                ([_session_id(a), _session_id(b)],),
            )
            found = {str(row["id"]): row["expires_at"] for row in cur.fetchall()}
    return {"a": found[_session_id(a)], "b": found[_session_id(b)]}


# ---- ログ ----


def test_ログにセッションIDとパスワードが含まれない(log_dir) -> None:  # type: ignore[no-untyped-def]
    username, _ = _make_user()
    a = _login(username)
    b = _login(username)
    text = "\n".join(p.read_text(encoding="utf-8") for p in log_dir.glob("*.log*"))
    assert f"ログイン成功 username={username}" in text
    assert _session_id(a) not in text and _session_id(b) not in text
    assert "secret" not in text
