from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path

from app.config import load_config
from app.logger import LOG_FILE
from app.repos import list_candidates
from app.services.mail_service import build_body, build_subject
from app.services.notice_service import (
    lookback_lower,
    run_once,
    start_datetime,
    threshold_at,
)
from helpers import (
    cleanup,
    insert_category,
    insert_notified_row,
    insert_schedule,
    insert_user,
    notified_exists,
    unique,
)


def _log_text(log_dir: Path) -> str:
    return (log_dir / LOG_FILE).read_text(encoding="utf-8")


def test_start_datetime_day_and_time() -> None:
    day_time = time(9, 0)
    day_start = start_datetime(date(2026, 8, 31), None, "day", day_time)
    assert day_start == datetime(2026, 8, 31, 9, 0)
    time_start = start_datetime(date(2026, 8, 31), time(14, 30), "time", day_time)
    assert time_start == datetime(2026, 8, 31, 14, 30)


def test_threshold_and_lookback() -> None:
    judged = datetime(2026, 8, 31, 10, 0)
    assert threshold_at(judged, 3) == datetime(2026, 8, 31, 10, 3)
    assert lookback_lower(judged, 30) == date(2026, 8, 1)


def test_mail_subject_and_body() -> None:
    assert build_subject("event", "会議") == "【予定】会議"
    assert build_subject("todo", "買い物") == "【TODO】買い物"
    body = build_body("会議", "2026-08-31 09:00")
    assert "会議" in body
    assert "2026-08-31 09:00" in body


def test_event_and_todo_conditions(log_dir: Path) -> None:
    judged = datetime(2026, 8, 31, 10, 0)
    user_id = insert_user(email="ok@example.com")
    cat_id = insert_category(user_id)
    event_id = insert_schedule(
        user_id,
        cat_id,
        title="対象予定",
        kind="event",
        granularity="day",
        start_date=date(2026, 8, 31),
    )
    todo_open = insert_schedule(
        user_id,
        cat_id,
        title="未実施TODO",
        kind="todo",
        granularity="day",
        start_date=date(2026, 8, 31),
        is_completed=False,
    )
    todo_done = insert_schedule(
        user_id,
        cat_id,
        title="実施済TODO",
        kind="todo",
        granularity="day",
        start_date=date(2026, 8, 31),
        is_completed=True,
    )
    no_need = insert_schedule(
        user_id,
        cat_id,
        title="通知不要",
        kind="event",
        granularity="day",
        start_date=date(2026, 8, 31),
        needs_notification=False,
    )
    deleted = insert_schedule(
        user_id,
        cat_id,
        title="削除済",
        kind="event",
        granularity="day",
        start_date=date(2026, 8, 31),
        is_deleted=True,
    )
    future = insert_schedule(
        user_id,
        cat_id,
        title="未来",
        kind="event",
        granularity="time",
        start_date=date(2026, 8, 31),
        start_time=time(18, 0),
    )
    sent: list[tuple[str, str, str]] = []

    def fake_send(_cfg: object, to_addr: str, subject: str, body: str) -> None:
        sent.append((to_addr, subject, body))

    try:
        run_once(now=judged, send=fake_send)
        sent_subjects = [item[1] for item in sent]
        assert any("対象予定" in s for s in sent_subjects)
        assert any("未実施TODO" in s for s in sent_subjects)
        assert all("実施済TODO" not in s for s in sent_subjects)
        assert all("通知不要" not in s for s in sent_subjects)
        assert all("削除済" not in s for s in sent_subjects)
        assert all("未来" not in s for s in sent_subjects)
        assert notified_exists(event_id)
        assert notified_exists(todo_open)
        assert not notified_exists(todo_done)
        assert not notified_exists(no_need)
        assert not notified_exists(deleted)
        assert not notified_exists(future)
    finally:
        cleanup(
            [event_id, todo_open, todo_done, no_need, deleted, future],
            [cat_id],
            [user_id],
        )


def test_already_notified_is_not_resent(log_dir: Path) -> None:
    judged = datetime(2026, 8, 31, 10, 0)
    user_id = insert_user()
    cat_id = insert_category(user_id)
    schedule_id = insert_schedule(
        user_id,
        cat_id,
        title="通知済の件",
        kind="event",
        start_date=date(2026, 8, 31),
    )
    insert_notified_row(schedule_id)
    sent: list[str] = []

    def fake_send(_cfg: object, to_addr: str, subject: str, _body: str) -> None:
        sent.append(subject)

    try:
        run_once(now=judged, send=fake_send)
        assert all("通知済の件" not in s for s in sent)
    finally:
        cleanup([schedule_id], [cat_id], [user_id])


def test_empty_email_and_deleted_user_not_marked(log_dir: Path) -> None:
    judged = datetime(2026, 8, 31, 10, 0)
    empty_id = insert_user(email="")
    deleted_id = insert_user(email="gone@example.com", is_deleted=True)
    empty_cat = insert_category(empty_id)
    deleted_cat = insert_category(deleted_id)
    empty_sched = insert_schedule(
        empty_id, empty_cat, title="空メール", start_date=date(2026, 8, 31)
    )
    deleted_sched = insert_schedule(
        deleted_id, deleted_cat, title="削除ユーザ", start_date=date(2026, 8, 31)
    )
    sent: list[str] = []

    def fake_send(_cfg: object, _to: str, subject: str, _body: str) -> None:
        sent.append(subject)

    try:
        run_once(now=judged, send=fake_send)
        assert all("空メール" not in s for s in sent)
        assert all("削除ユーザ" not in s for s in sent)
        assert not notified_exists(empty_sched)
        assert not notified_exists(deleted_sched)
        log = _log_text(log_dir)
        assert "メールアドレス空" in log
        assert "所有者論理削除済み" in log
    finally:
        cleanup(
            [empty_sched, deleted_sched],
            [empty_cat, deleted_cat],
            [empty_id, deleted_id],
        )


def test_send_failure_does_not_mark_and_continues(log_dir: Path) -> None:
    judged = datetime(2026, 8, 31, 10, 0)
    user_id = insert_user()
    cat_id = insert_category(user_id)
    fail_id = insert_schedule(
        user_id, cat_id, title="失敗する", start_date=date(2026, 8, 31)
    )
    ok_id = insert_schedule(
        user_id, cat_id, title="成功する", start_date=date(2026, 8, 31)
    )
    sent: list[str] = []

    def fake_send(_cfg: object, _to: str, subject: str, _body: str) -> None:
        if "失敗する" in subject:
            raise OSError("smtp down")
        sent.append(subject)

    try:
        run_once(now=judged, send=fake_send)
        assert any("成功する" in s for s in sent)
        assert not notified_exists(fail_id)
        assert notified_exists(ok_id)
        log = _log_text(log_dir)
        assert "送信失敗" in log
        assert "OSError" in log
    finally:
        cleanup([fail_id, ok_id], [cat_id], [user_id])


def test_time_granularity_threshold() -> None:
    judged = datetime(2026, 8, 31, 10, 0)
    user_id = insert_user()
    cat_id = insert_category(user_id)
    due_id = insert_schedule(
        user_id,
        cat_id,
        title="直前",
        kind="event",
        granularity="time",
        start_date=date(2026, 8, 31),
        start_time=time(10, 2),
    )
    same_id = insert_schedule(
        user_id,
        cat_id,
        title="しきいと同じ",
        kind="event",
        granularity="time",
        start_date=date(2026, 8, 31),
        start_time=time(10, 3),
    )
    sent: list[str] = []

    def fake_send(_cfg: object, _to: str, subject: str, _body: str) -> None:
        sent.append(subject)

    try:
        run_once(now=judged, send=fake_send)
        assert any("直前" in s for s in sent)
        assert all("しきいと同じ" not in s for s in sent)
        assert notified_exists(due_id)
        assert not notified_exists(same_id)
    finally:
        cleanup([due_id, same_id], [cat_id], [user_id])


def test_lookback_excludes_old_start_dates() -> None:
    judged = datetime(2026, 8, 31, 10, 0)
    lower = lookback_lower(judged, 30)
    user_id = insert_user()
    cat_id = insert_category(user_id)
    old_id = insert_schedule(
        user_id, cat_id, title="古い", start_date=date(2026, 8, 1)
    )
    older_id = insert_schedule(
        user_id, cat_id, title="もっと古い", start_date=date(2026, 7, 31)
    )
    in_id = insert_schedule(
        user_id, cat_id, title="範囲内", start_date=date(2026, 8, 2)
    )
    try:
        rows = list_candidates(lower)
        ids = {row.id for row in rows}
        assert in_id in ids
        assert old_id not in ids
        assert older_id not in ids
    finally:
        cleanup([old_id, older_id, in_id], [cat_id], [user_id])


def test_log_omits_smtp_password(log_dir: Path) -> None:
    judged = datetime(2026, 8, 31, 10, 0)
    user_id = insert_user()
    cat_id = insert_category(user_id)
    schedule_id = insert_schedule(
        user_id, cat_id, title="ログ", start_date=date(2026, 8, 31)
    )

    def fake_send(_cfg: object, _to: str, _subject: str, _body: str) -> None:
        return None

    try:
        run_once(now=judged, send=fake_send)
        cfg = load_config()
        log = _log_text(log_dir)
        assert cfg.smtp_password
        assert cfg.smtp_password not in log
        assert "判定開始" in log
        assert "送信成功" in log
    finally:
        cleanup([schedule_id], [cat_id], [user_id])


def test_second_run_does_not_resend(log_dir: Path) -> None:
    judged = datetime(2026, 8, 31, 10, 0)
    user_id = insert_user()
    cat_id = insert_category(user_id)
    schedule_id = insert_schedule(
        user_id,
        cat_id,
        title=unique("再送"),
        start_date=date(2026, 8, 31),
    )
    sent: list[str] = []

    def fake_send(_cfg: object, _to: str, subject: str, _body: str) -> None:
        sent.append(subject)

    try:
        run_once(now=judged, send=fake_send)
        first = len(sent)
        assert first >= 1
        run_once(now=judged, send=fake_send)
        assert len(sent) == first
    finally:
        cleanup([schedule_id], [cat_id], [user_id])
