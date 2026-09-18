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


def test_settings_unauthenticated() -> None:
    client = TestClient(app)
    res = client.get("/settings")
    assert res.status_code == 200
    body = res.json()
    assert "login_url" in body
    assert "menu_url" in body
    assert body["icon_system"].startswith("data:image/")
    assert body["icon_back"].startswith("data:image/")
    assert "session_id" not in res.text


def test_schedules_require_login() -> None:
    client = TestClient(app)
    res = client.get("/schedules", params={"start_date": "2026-08-01", "end_date": "2026-08-31"})
    assert res.status_code == 401
    assert res.json() == {"detail": "未ログイン"}


def test_schedules_require_assignment() -> None:
    ensure_feature()
    user_id = insert_user(unique("noas"))
    client = TestClient(app)
    cfg = load_config()
    session_id = insert_session(user_id, cfg.session_timeout_minutes)
    client.cookies.set("session_id", str(session_id))
    res = client.get("/schedules", params={"start_date": "2026-08-01", "end_date": "2026-08-31"})
    assert res.status_code == 403
    assert res.json() == {"detail": "権限がありません"}


def test_category_crud_and_duplicate(log_dir: Path) -> None:
    _user_id, client = _operator()
    created = client.post("/categories", json={"name": unique("仕事"), "color": "#4DA3FF"})
    assert created.status_code == 201
    cat_id = created.json()["id"]
    assert created.json()["is_deleted"] is False

    dup = client.post("/categories", json={"name": created.json()["name"], "color": "#FF9A4A"})
    assert dup.status_code == 409
    assert dup.json() == {"detail": "保存できませんでした"}

    empty = client.post("/categories", json={"name": "  ", "color": "#4DA3FF"})
    assert empty.status_code == 400

    bad_color = client.post("/categories", json={"name": unique("色"), "color": "blue"})
    assert bad_color.status_code == 400

    patched = client.patch(f"/categories/{cat_id}", json={"name": unique("更新"), "color": "#8B7CFF"})
    assert patched.status_code == 200
    assert patched.json()["color"] == "#8B7CFF"

    deleted = client.delete(f"/categories/{cat_id}")
    assert deleted.status_code == 204
    again = client.delete(f"/categories/{cat_id}")
    assert again.status_code == 404

    listed = client.get("/categories")
    assert listed.status_code == 200
    assert all(item["id"] != cat_id for item in listed.json()["items"])

    with_deleted = client.get("/categories", params={"include_deleted": "true"})
    ids = {item["id"] for item in with_deleted.json()["items"]}
    assert cat_id in ids

    text = _log_text(log_dir)
    assert "カテゴリ追加要求" in text
    assert "カテゴリ追加成功" in text
    assert "名称重複" in text
    assert "session_id" not in text


def test_preferences_defaults_and_save() -> None:
    _user_id, client = _operator()
    initial = client.get("/preferences")
    assert initial.status_code == 200
    assert initial.json() == {
        "week_starts_on": "sunday",
        "show_deleted": False,
        "hidden_category_ids": [],
    }
    cat = client.post("/categories", json={"name": unique("隠"), "color": "#4DA3FF"}).json()
    saved = client.put(
        "/preferences",
        json={
            "week_starts_on": "monday",
            "show_deleted": True,
            "hidden_category_ids": [cat["id"]],
        },
    )
    assert saved.status_code == 200
    again = client.get("/preferences")
    assert again.json()["week_starts_on"] == "monday"
    assert again.json()["show_deleted"] is True
    assert again.json()["hidden_category_ids"] == [cat["id"]]

    bad_week = client.put(
        "/preferences",
        json={"week_starts_on": "friday", "show_deleted": False, "hidden_category_ids": []},
    )
    assert bad_week.status_code == 400

    other = insert_user(unique("other"))
    assign_feature(other)
    other_client = TestClient(app)
    cfg = load_config()
    other_client.cookies.set("session_id", str(insert_session(other, cfg.session_timeout_minutes)))
    other_cat = other_client.post("/categories", json={"name": unique("他"), "color": "#4DA3FF"}).json()
    stolen = client.put(
        "/preferences",
        json={
            "week_starts_on": "sunday",
            "show_deleted": False,
            "hidden_category_ids": [other_cat["id"]],
        },
    )
    assert stolen.status_code == 400


def test_schedule_crud_sort_overlap_and_completion(log_dir: Path) -> None:
    _user_id, client = _operator()
    cat = client.post("/categories", json={"name": unique("予定"), "color": "#4DA3FF"}).json()
    cat_id = cat["id"]

    day = client.post(
        "/schedules",
        json={
            "title": "終日会議",
            "kind": "event",
            "granularity": "day",
            "start_date": "2026-08-10",
            "end_date": "2026-08-12",
            "category_id": cat_id,
            "needs_notification": False,
        },
    )
    assert day.status_code == 201
    assert day.json()["start_time"] is None
    assert day.json()["is_completed"] is None
    day_id = day.json()["id"]

    todo = client.post(
        "/schedules",
        json={
            "title": "資料作成",
            "kind": "todo",
            "granularity": "time",
            "start_date": "2026-08-10",
            "end_date": "2026-08-10",
            "start_time": "09:00",
            "end_time": "10:00",
            "category_id": cat_id,
            "needs_notification": False,
        },
    )
    assert todo.status_code == 201
    assert todo.json()["is_completed"] is False
    todo_id = todo.json()["id"]

    later = client.post(
        "/schedules",
        json={
            "title": "午後",
            "kind": "event",
            "granularity": "time",
            "start_date": "2026-08-10",
            "end_date": "2026-08-10",
            "start_time": "13:00",
            "end_time": "14:00",
            "category_id": cat_id,
            "needs_notification": False,
        },
    )
    assert later.status_code == 201

    listed = client.get("/schedules", params={"start_date": "2026-08-11", "end_date": "2026-08-11"})
    titles = [item["title"] for item in listed.json()["items"]]
    assert titles == ["終日会議"]

    full = client.get("/schedules", params={"start_date": "2026-08-10", "end_date": "2026-08-10"})
    order = [item["title"] for item in full.json()["items"]]
    assert order == ["終日会議", "資料作成", "午後"]

    before = client.post(
        "/schedules",
        json={
            "title": "不正",
            "kind": "event",
            "granularity": "time",
            "start_date": "2026-08-10",
            "end_date": "2026-08-10",
            "start_time": "11:00",
            "end_time": "10:00",
            "category_id": cat_id,
            "needs_notification": False,
        },
    )
    assert before.status_code == 400

    timed_on_day = client.post(
        "/schedules",
        json={
            "title": "時刻付き日単位",
            "kind": "event",
            "granularity": "day",
            "start_date": "2026-08-10",
            "end_date": "2026-08-10",
            "start_time": "09:00",
            "end_time": "10:00",
            "category_id": cat_id,
            "needs_notification": False,
        },
    )
    assert timed_on_day.status_code == 400

    event_complete = client.patch(f"/schedules/{day_id}/completion", json={"is_completed": True})
    assert event_complete.status_code == 409
    assert event_complete.json() == {"detail": "保存できませんでした"}

    done = client.patch(f"/schedules/{todo_id}/completion", json={"is_completed": True})
    assert done.status_code == 200
    assert done.json()["is_completed"] is True

    to_todo = client.patch(
        f"/schedules/{day_id}",
        json={
            "title": "終日会議",
            "kind": "todo",
            "granularity": "day",
            "start_date": "2026-08-10",
            "end_date": "2026-08-12",
            "category_id": cat_id,
            "needs_notification": False,
        },
    )
    assert to_todo.status_code == 200
    assert to_todo.json()["is_completed"] is False

    to_event = client.patch(
        f"/schedules/{todo_id}",
        json={
            "title": "資料作成",
            "kind": "event",
            "granularity": "time",
            "start_date": "2026-08-10",
            "end_date": "2026-08-10",
            "start_time": "09:00",
            "end_time": "10:00",
            "category_id": cat_id,
            "needs_notification": False,
        },
    )
    assert to_event.status_code == 200
    assert to_event.json()["is_completed"] is None

    deleted = client.delete(f"/schedules/{later.json()['id']}")
    assert deleted.status_code == 204
    after = client.get("/schedules", params={"start_date": "2026-08-10", "end_date": "2026-08-10"})
    assert all(item["title"] != "午後" for item in after.json()["items"])

    text = _log_text(log_dir)
    assert "スケジュール追加要求" in text
    assert "スケジュール追加成功" in text
    assert "終了が開始より前" in text
    assert "予定への実施状態変更" in text
    assert "session_id" not in text


def test_other_user_schedule_is_404() -> None:
    _user_id, client = _operator()
    other_id = insert_user(unique("peer"))
    assign_feature(other_id)
    other = TestClient(app)
    cfg = load_config()
    other.cookies.set("session_id", str(insert_session(other_id, cfg.session_timeout_minutes)))
    cat = other.post("/categories", json={"name": unique("他"), "color": "#4DA3FF"}).json()
    created = other.post(
        "/schedules",
        json={
            "title": "秘密",
            "kind": "event",
            "granularity": "day",
            "start_date": "2026-08-20",
            "end_date": "2026-08-20",
            "category_id": cat["id"],
            "needs_notification": False,
        },
    )
    schedule_id = created.json()["id"]
    listed = client.get("/schedules", params={"start_date": "2026-08-20", "end_date": "2026-08-20"})
    assert all(item["id"] != schedule_id for item in listed.json()["items"])
    missing = client.patch(
        f"/schedules/{schedule_id}",
        json={
            "title": "奪取",
            "kind": "event",
            "granularity": "day",
            "start_date": "2026-08-20",
            "end_date": "2026-08-20",
            "category_id": cat["id"],
            "needs_notification": False,
        },
    )
    assert missing.status_code == 404
    assert missing.json() == {"detail": "対象がありません"}


def test_deleted_category_keeps_schedule() -> None:
    _user_id, client = _operator()
    cat = client.post("/categories", json={"name": unique("残"), "color": "#4DA3FF"}).json()
    created = client.post(
        "/schedules",
        json={
            "title": "残る予定",
            "kind": "event",
            "granularity": "day",
            "start_date": "2026-09-01",
            "end_date": "2026-09-01",
            "category_id": cat["id"],
            "needs_notification": False,
        },
    )
    assert created.status_code == 201
    assert client.delete(f"/categories/{cat['id']}").status_code == 204
    listed = client.get("/schedules", params={"start_date": "2026-09-01", "end_date": "2026-09-01"})
    assert listed.json()["items"][0]["title"] == "残る予定"
    assert listed.json()["items"][0]["category_id"] == cat["id"]


def test_user_holiday_crud_and_duplicate(log_dir: Path) -> None:
    _user_id, client = _operator()
    created = client.post(
        "/user-holidays",
        json={"holiday_date": "2026-08-15", "name": "会社休業"},
    )
    assert created.status_code == 201
    holiday_id = created.json()["id"]

    same_national = client.post(
        "/user-holidays",
        json={"holiday_date": "2026-01-01", "name": "社内休み"},
    )
    assert same_national.status_code == 201

    dup = client.post(
        "/user-holidays",
        json={"holiday_date": "2026-08-15", "name": "重複"},
    )
    assert dup.status_code == 409
    assert dup.json() == {"detail": "保存できませんでした"}

    patched = client.patch(
        f"/user-holidays/{holiday_id}",
        json={"holiday_date": "2026-08-16", "name": "振替休業"},
    )
    assert patched.status_code == 200
    assert patched.json()["holiday_date"] == "2026-08-16"

    listed = client.get("/user-holidays", params={"start_date": "2026-08-01", "end_date": "2026-08-31"})
    dates = [item["holiday_date"] for item in listed.json()["items"]]
    assert dates == sorted(dates)
    assert "2026-08-16" in dates

    assert client.delete(f"/user-holidays/{holiday_id}").status_code == 204
    after = client.get("/user-holidays")
    assert all(item["id"] != holiday_id for item in after.json()["items"])

    text = _log_text(log_dir)
    assert "ユーザ休日追加要求" in text
    assert "ユーザ休日追加成功" in text
    assert "年月日重複" in text
    assert "session_id" not in text


def test_holidays_api_and_bad_query() -> None:
    _user_id, client = _operator()
    ok = client.get("/holidays", params={"start_date": "2026-05-01", "end_date": "2026-05-07"})
    assert ok.status_code == 200
    dates = [item["date"] for item in ok.json()["items"]]
    assert "2026-05-06" in dates
    bad = client.get("/holidays", params={"start_date": "2026-05-07", "end_date": "2026-05-01"})
    assert bad.status_code == 400
    missing = client.get("/holidays")
    assert missing.status_code == 400
