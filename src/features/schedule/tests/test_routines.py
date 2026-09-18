from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import load_config
from app.logger import LOG_FILE
from app.main import app
from app.services.routine_service import apply_date, base_date
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
    created = client.post("/categories", json={"name": unique("定例"), "color": "#4DA3FF"})
    assert created.status_code == 201
    return int(created.json()["id"])


def test_base_date_last_day_and_missing_day() -> None:
    assert base_date(2026, 2, "date", "last_day", None, None, None, None) == date(2026, 2, 28)
    assert base_date(2026, 2, "date", "day_of_month", 31, None, None, None) is None
    assert base_date(2026, 8, "date", "day_of_month", 15, None, None, None) == date(2026, 8, 15)


def test_base_date_nth_and_from_last() -> None:
    # August 2026: 1st is Saturday. 1st Monday is Aug 3. 5th Monday is Aug 31.
    assert base_date(2026, 8, "weekday", None, None, "nth", 1, "monday") == date(2026, 8, 3)
    assert base_date(2026, 8, "weekday", None, None, "nth", 5, "monday") == date(2026, 8, 31)
    assert base_date(2026, 2, "weekday", None, None, "nth", 5, "monday") is None
    assert base_date(2026, 8, "weekday", None, None, "nth_from_last", 1, "monday") == date(2026, 8, 31)
    assert base_date(2026, 8, "weekday", None, None, "nth_from_last", 2, "monday") == date(2026, 8, 24)


def test_apply_date_shift_holiday_later() -> None:
    # 2026-01-01 is 元日 (Thursday). Shift later to Jan 2.
    shifted = apply_date(date(2026, 1, 1), True, "later", ["holiday"])
    assert shifted == date(2026, 1, 2)
    unchanged = apply_date(date(2026, 1, 2), True, "later", ["holiday"])
    assert unchanged == date(2026, 1, 2)
    none_needed = apply_date(date(2026, 1, 15), False, None, [])
    assert none_needed == date(2026, 1, 15)


def test_apply_date_shift_sunday_earlier() -> None:
    # 2026-08-02 is Sunday.
    shifted = apply_date(date(2026, 8, 2), True, "earlier", ["sunday"])
    assert shifted == date(2026, 8, 1)


def test_apply_date_gives_up_after_31_days() -> None:
    result = apply_date(
        date(2026, 8, 1),
        True,
        "later",
        ["holiday", "sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"],
    )
    assert result is None


def test_holidays_shift_does_not_call_network() -> None:
    with patch("urllib.request.urlopen") as mocked:
        apply_date(date(2026, 1, 1), True, "later", ["holiday"])
        mocked.assert_not_called()


def test_routine_crud_and_apply(log_dir: Path) -> None:
    _user_id, client = _operator()
    cat_id = _category(client)
    created = client.post(
        "/routines",
        json={
            "title": "支払い",
            "detail": "メモ",
            "kind": "todo",
            "category_id": cat_id,
            "needs_notification": False,
            "occurrence_type": "date",
            "date_rule": "day_of_month",
            "day_of_month": 15,
            "adjust_excluded": False,
            "months": [8, 1],
            "exclusions": [],
        },
    )
    assert created.status_code == 201
    routine_id = created.json()["id"]
    assert created.json()["months"] == [1, 8]
    assert created.json()["detail"] == "メモ"
    listed = client.get("/routines")
    assert listed.status_code == 200
    assert any(item["id"] == routine_id for item in listed.json()["items"])

    empty = client.post(
        "/routines",
        json={
            "title": "  ",
            "kind": "event",
            "category_id": cat_id,
            "needs_notification": False,
            "occurrence_type": "date",
            "date_rule": "last_day",
            "adjust_excluded": False,
            "months": [1],
        },
    )
    assert empty.status_code == 400

    applied = client.post(f"/routines/{routine_id}/apply", json={"year": 2026, "month": 8})
    assert applied.status_code == 200
    items = applied.json()["items"]
    assert len(items) == 1
    assert items[0]["start_date"] == "2026-08-15"
    assert items[0]["end_date"] == "2026-08-15"
    assert items[0]["granularity"] == "day"
    assert items[0]["kind"] == "todo"
    assert items[0]["is_completed"] is False
    assert items[0]["routine_id"] == routine_id
    assert items[0]["detail"] == "メモ"
    assert items[0]["location"] is None

    again = client.post(f"/routines/{routine_id}/apply", json={"year": 2026, "month": 8})
    assert again.status_code == 200
    assert again.json()["items"] == []

    skipped_month = client.post(f"/routines/{routine_id}/apply", json={"year": 2026, "month": 3})
    assert skipped_month.status_code == 200
    assert skipped_month.json()["items"] == []

    schedules = client.get("/schedules", params={"start_date": "2026-08-01", "end_date": "2026-08-31"})
    assert schedules.status_code == 200
    found = [item for item in schedules.json()["items"] if item["routine_id"] == routine_id]
    assert len(found) == 1

    deleted = client.delete(f"/routines/{routine_id}")
    assert deleted.status_code == 204
    listed_after = client.get("/routines")
    assert all(item["id"] != routine_id for item in listed_after.json()["items"])
    still = client.get("/schedules", params={"start_date": "2026-08-01", "end_date": "2026-08-31"})
    assert any(item["id"] == found[0]["id"] for item in still.json()["items"])

    missing = client.post(f"/routines/{routine_id}/apply", json={"year": 2026, "month": 8})
    assert missing.status_code == 404

    text = _log_text(log_dir)
    assert "ルーチン追加要求" in text
    assert "ルーチン追加成功" in text
    assert "同一ルーチン識別が指定年月に既にある" in text
    assert "反映月外" in text
    assert "session_id" not in text


def test_apply_all_continues_when_one_skips() -> None:
    _user_id, client = _operator()
    cat_id = _category(client)
    first = client.post(
        "/routines",
        json={
            "title": "A",
            "kind": "event",
            "category_id": cat_id,
            "needs_notification": False,
            "occurrence_type": "date",
            "date_rule": "last_day",
            "adjust_excluded": False,
            "months": [4],
        },
    ).json()
    second = client.post(
        "/routines",
        json={
            "title": "B",
            "kind": "event",
            "category_id": cat_id,
            "needs_notification": False,
            "occurrence_type": "date",
            "date_rule": "day_of_month",
            "day_of_month": 10,
            "adjust_excluded": False,
            "months": [8],
        },
    ).json()
    result = client.post("/routines/apply-all", json={"year": 2026, "month": 8})
    assert result.status_code == 200
    titles = [item["title"] for item in result.json()["items"]]
    assert titles == ["B"]
    assert result.json()["items"][0]["routine_id"] == second["id"]
    assert first["id"] not in {item["routine_id"] for item in result.json()["items"]}


def test_manual_schedule_has_null_routine_id() -> None:
    _user_id, client = _operator()
    cat_id = _category(client)
    created = client.post(
        "/schedules",
        json={
            "title": "手入力",
            "kind": "event",
            "granularity": "day",
            "start_date": "2026-08-20",
            "end_date": "2026-08-20",
            "category_id": cat_id,
            "needs_notification": False,
        },
    )
    assert created.status_code == 201
    assert created.json()["routine_id"] is None
    patched = client.patch(
        f"/schedules/{created.json()['id']}",
        json={
            "title": "手入力2",
            "kind": "event",
            "granularity": "day",
            "start_date": "2026-08-20",
            "end_date": "2026-08-20",
            "category_id": cat_id,
            "needs_notification": False,
        },
    )
    assert patched.status_code == 200
    assert patched.json()["routine_id"] is None
    assert patched.json()["title"] == "手入力2"


def test_routine_update_does_not_change_schedules(log_dir: Path) -> None:
    _user_id, client = _operator()
    cat_id = _category(client)
    created = client.post(
        "/routines",
        json={
            "title": "旧題",
            "detail": "旧メモ",
            "kind": "todo",
            "category_id": cat_id,
            "needs_notification": False,
            "occurrence_type": "date",
            "date_rule": "day_of_month",
            "day_of_month": 15,
            "adjust_excluded": False,
            "months": [8],
        },
    )
    assert created.status_code == 201
    routine_id = created.json()["id"]
    applied = client.post(f"/routines/{routine_id}/apply", json={"year": 2026, "month": 8})
    assert applied.status_code == 200
    schedule_id = applied.json()["items"][0]["id"]

    updated = client.patch(
        f"/routines/{routine_id}",
        json={
            "title": "新題",
            "detail": "新メモ",
            "kind": "event",
            "category_id": cat_id,
            "needs_notification": False,
            "occurrence_type": "date",
            "date_rule": "last_day",
            "adjust_excluded": True,
            "shift_direction": "later",
            "months": [8, 12],
            "exclusions": ["holiday"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["id"] == routine_id
    assert updated.json()["title"] == "新題"
    assert updated.json()["detail"] == "新メモ"
    assert updated.json()["kind"] == "event"
    assert updated.json()["date_rule"] == "last_day"
    assert updated.json()["day_of_month"] is None
    assert updated.json()["months"] == [8, 12]
    assert updated.json()["exclusions"] == ["holiday"]
    assert updated.json()["adjust_excluded"] is True

    listed = client.get("/routines")
    found = next(item for item in listed.json()["items"] if item["id"] == routine_id)
    assert found["title"] == "新題"

    schedules = client.get("/schedules", params={"start_date": "2026-08-01", "end_date": "2026-08-31"})
    kept = next(item for item in schedules.json()["items"] if item["id"] == schedule_id)
    assert kept["title"] == "旧題"
    assert kept["detail"] == "旧メモ"
    assert kept["kind"] == "todo"
    assert kept["routine_id"] == routine_id
    assert kept["start_date"] == "2026-08-15"

    invalid = client.patch(
        f"/routines/{routine_id}",
        json={
            "title": "  ",
            "kind": "event",
            "category_id": cat_id,
            "needs_notification": False,
            "occurrence_type": "date",
            "date_rule": "last_day",
            "adjust_excluded": False,
            "months": [8],
        },
    )
    assert invalid.status_code == 400

    client.delete(f"/routines/{routine_id}")
    gone = client.patch(
        f"/routines/{routine_id}",
        json={
            "title": "後",
            "kind": "event",
            "category_id": cat_id,
            "needs_notification": False,
            "occurrence_type": "date",
            "date_rule": "last_day",
            "adjust_excluded": False,
            "months": [8],
        },
    )
    assert gone.status_code == 404

    text = _log_text(log_dir)
    assert "ルーチン更新要求" in text
    assert "ルーチン更新成功" in text
    assert "ルーチン更新失敗" in text
    assert "session_id" not in text
