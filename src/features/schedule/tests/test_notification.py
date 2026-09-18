from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import load_config
from app.logger import LOG_FILE
from app.main import app
from helpers import assign_feature, ensure_feature, insert_session, insert_user, unique


def _log_text(log_dir: Path) -> str:
    return (log_dir / LOG_FILE).read_text(encoding="utf-8")


def _operator() -> tuple[int, TestClient]:
    ensure_feature()
    user_id = insert_user(unique("op"))
    assign_feature(user_id)
    client = TestClient(app)
    cfg = load_config()
    session_id = insert_session(user_id, cfg.session_timeout_minutes)
    client.cookies.set("session_id", str(session_id))
    return user_id, client


def _category(client: TestClient) -> int:
    created = client.post("/categories", json={"name": unique("通知"), "color": "#4DA3FF"})
    assert created.status_code == 201
    return int(created.json()["id"])


def test_schedule_needs_notification_create_update_and_reject(log_dir: Path) -> None:
    _user_id, client = _operator()
    cat_id = _category(client)
    created = client.post(
        "/schedules",
        json={
            "title": "通知あり",
            "kind": "event",
            "granularity": "day",
            "start_date": "2026-08-20",
            "end_date": "2026-08-20",
            "category_id": cat_id,
            "needs_notification": True,
        },
    )
    assert created.status_code == 201
    assert created.json()["needs_notification"] is True

    listed = client.get("/schedules", params={"start_date": "2026-08-20", "end_date": "2026-08-20"})
    found = next(item for item in listed.json()["items"] if item["id"] == created.json()["id"])
    assert found["needs_notification"] is True

    patched = client.patch(
        f"/schedules/{created.json()['id']}",
        json={
            "title": "通知なし",
            "kind": "event",
            "granularity": "day",
            "start_date": "2026-08-20",
            "end_date": "2026-08-20",
            "category_id": cat_id,
            "needs_notification": False,
        },
    )
    assert patched.status_code == 200
    assert patched.json()["needs_notification"] is False

    missing = client.post(
        "/schedules",
        json={
            "title": "欠落",
            "kind": "event",
            "granularity": "day",
            "start_date": "2026-08-21",
            "end_date": "2026-08-21",
            "category_id": cat_id,
        },
    )
    assert missing.status_code == 400

    bad = client.post(
        "/schedules",
        json={
            "title": "不正",
            "kind": "event",
            "granularity": "day",
            "start_date": "2026-08-21",
            "end_date": "2026-08-21",
            "category_id": cat_id,
            "needs_notification": "yes",
        },
    )
    assert bad.status_code == 400

    text = _log_text(log_dir)
    assert "needs_notification=True" in text
    assert "needs_notification=False" in text
    assert "session_id" not in text


def test_routine_needs_notification_and_apply_copies_value() -> None:
    _user_id, client = _operator()
    cat_id = _category(client)
    created = client.post(
        "/routines",
        json={
            "title": "通知ルーチン",
            "kind": "todo",
            "category_id": cat_id,
            "occurrence_type": "date",
            "date_rule": "day_of_month",
            "day_of_month": 15,
            "adjust_excluded": False,
            "months": [8],
            "needs_notification": True,
        },
    )
    assert created.status_code == 201
    assert created.json()["needs_notification"] is True
    routine_id = created.json()["id"]

    listed = client.get("/routines")
    found = next(item for item in listed.json()["items"] if item["id"] == routine_id)
    assert found["needs_notification"] is True

    applied = client.post(f"/routines/{routine_id}/apply", json={"year": 2026, "month": 8})
    assert applied.status_code == 200
    assert applied.json()["items"][0]["needs_notification"] is True
    assert applied.json()["items"][0]["routine_id"] == routine_id

    updated = client.patch(
        f"/routines/{routine_id}",
        json={
            "title": "通知ルーチン",
            "kind": "todo",
            "category_id": cat_id,
            "occurrence_type": "date",
            "date_rule": "day_of_month",
            "day_of_month": 15,
            "adjust_excluded": False,
            "months": [8],
            "needs_notification": False,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["needs_notification"] is False

    schedules = client.get("/schedules", params={"start_date": "2026-08-15", "end_date": "2026-08-15"})
    kept = next(item for item in schedules.json()["items"] if item["routine_id"] == routine_id)
    assert kept["needs_notification"] is True

    missing = client.post(
        "/routines",
        json={
            "title": "欠落",
            "kind": "event",
            "category_id": cat_id,
            "occurrence_type": "date",
            "date_rule": "last_day",
            "adjust_excluded": False,
            "months": [8],
        },
    )
    assert missing.status_code == 400
