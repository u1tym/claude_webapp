from __future__ import annotations

from pathlib import Path

from app.logger import LOG_FILE
from app.repos import insert_user
from app.security import hash_password
from test_api import _client_as, _operator, _unique


def _log_text(log_dir: Path) -> str:
    return (log_dir / LOG_FILE).read_text(encoding="utf-8")


def test_user_email_create_update_and_reject(log_dir: Path) -> None:
    op_id, _ = _operator()
    client = _client_as(op_id)
    name = _unique("mail")
    created = client.post(
        "/users",
        json={"username": name, "password": "pw-secret", "email": "one@example.com"},
    )
    assert created.status_code == 201
    assert created.json()["email"] == "one@example.com"
    assert "password" not in created.json()

    listed = client.get("/users")
    found = next(item for item in listed.json()["items"] if item["id"] == created.json()["id"])
    assert found["email"] == "one@example.com"
    assert "password" not in found

    patched = client.patch(
        f"/users/{created.json()['id']}",
        json={"username": name, "email": "two@example.com"},
    )
    assert patched.status_code == 200
    assert patched.json()["email"] == "two@example.com"

    missing = client.post("/users", json={"username": _unique("noem"), "password": "pw"})
    assert missing.status_code == 400

    empty = client.post(
        "/users",
        json={"username": _unique("empty"), "password": "pw", "email": ""},
    )
    assert empty.status_code == 400

    bad = client.post(
        "/users",
        json={"username": _unique("bad"), "password": "pw", "email": "nodomain"},
    )
    assert bad.status_code == 400

    at_only = client.post(
        "/users",
        json={"username": _unique("at"), "password": "pw", "email": "@x"},
    )
    assert at_only.status_code == 400

    patch_bad = client.patch(
        f"/users/{created.json()['id']}",
        json={"username": name, "email": "a@"},
    )
    assert patch_bad.status_code == 400

    text = _log_text(log_dir)
    assert "email=one@example.com" in text
    assert "email=two@example.com" in text
    assert "pw-secret" not in text


def test_same_email_allowed() -> None:
    op_id, _ = _operator()
    client = _client_as(op_id)
    shared = "shared@example.com"
    first = client.post(
        "/users",
        json={"username": _unique("e1"), "password": "pw", "email": shared},
    )
    second = client.post(
        "/users",
        json={"username": _unique("e2"), "password": "pw", "email": shared},
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["email"] == shared
    assert second.json()["email"] == shared


def test_list_includes_email_not_password() -> None:
    op_id, _ = _operator()
    insert_user(_unique("listed"), hash_password("x"), "shown@example.com")
    client = _client_as(op_id)
    listed = client.get("/users")
    assert listed.status_code == 200
    found = next(item for item in listed.json()["items"] if item["email"] == "shown@example.com")
    assert found["email"] == "shown@example.com"
    assert "password" not in found
    assert "password_hash" not in found
