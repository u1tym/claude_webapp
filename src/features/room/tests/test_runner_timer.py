"""定期実行ジョブの、基準日の判定（祝日の扱い × 実行日の取り方）と、機器の個別切替の実行（T-023）。"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, time, timedelta
from pathlib import Path

import pytest

from app.db import get_conn
from app.logger import LOG_FILE
from app.repos import RoomScheduleRow
from app.services import runner_service
from app.services.runner_service import base_day, run_once, select_due
from fakes import ID_BEDSIDE, ID_DOOR, ID_INDIRECT, ID_INDOOR, FakeSwitchBot, failure
from helpers import insert_user, unique
from test_runner import at, last_run, make

# 2026-11 の曜日: 1日=日、2日=月、3日=火（文化の日・祝日）、4日=水、5日=木、6日=金、7日=土、8日=日、9日=月
SUN1, MON2, TUE3, WED4, THU5, FRI6, SAT7, SUN8, MON9 = (date(2026, 11, d) for d in range(1, 10))
MON_FRI = (1, 2, 3, 4, 5)
SAT_SUN = (6, 7)


def row(
    weekdays: tuple[int, ...],
    holiday_mode: str = "none",
    day_shift: str = "same",
    condition: str = "weekdays",
) -> RoomScheduleRow:
    return RoomScheduleRow(
        id=1,
        created_by_user_id=1,
        condition_type=condition,
        weekdays=weekdays,
        holiday_mode=holiday_mode,
        day_shift=day_shift,
        run_time=time(7, 0),
        action_type="scene",
        scene="out",
        device=None,
        target_state=None,
        is_enabled=True,
        last_run_at=None,
        last_run_result=None,
        last_failed_devices=(),
    )


def matches(schedule: RoomScheduleRow, day: date) -> bool:
    return runner_service._condition_matches(schedule, day)[0]


@pytest.fixture
def user_id() -> Iterator[int]:
    uid = insert_user(unique("room_runner_timer"))
    yield uid
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM room.room_schedules WHERE created_by_user_id = %s", (uid,))


# ---- 基準日 ----


def test_基準日は_当日_前の日は翌日_次の日は前日() -> None:
    assert base_day(row(MON_FRI, day_shift="same"), TUE3) == TUE3
    assert base_day(row(MON_FRI, day_shift="before"), TUE3) == WED4  # の前の日 = 翌日が基準日の日に実行
    assert base_day(row(MON_FRI, day_shift="after"), TUE3) == MON2  # の次の日 = 前日が基準日の日に実行


# ---- 祝日の扱い × 実行日の取り方（9通り） ----


@pytest.mark.parametrize(
    "day, expected",
    [
        (MON2, True),
        (TUE3, True),  # 祝日でも、指定した曜日なら実行する（祝日は関係しない）
        (SAT7, False),
        (SUN8, False),
    ],
)
def test_none_same_指定した曜日のみ(day: date, expected: bool) -> None:
    assert matches(row(MON_FRI, "none", "same"), day) is expected


@pytest.mark.parametrize(
    "day, expected",
    [
        (MON2, True),
        (TUE3, False),  # 平日でも祝日は実行しない
        (WED4, True),
        (SAT7, False),
    ],
)
def test_exclude_same_祝日は実行しない(day: date, expected: bool) -> None:
    assert matches(row(MON_FRI, "exclude", "same"), day) is expected


@pytest.mark.parametrize(
    "day, expected",
    [
        (SAT7, True),
        (SUN8, True),
        (TUE3, True),  # 平日の祝日も実行する
        (WED4, False),  # 指定外の平日
        (MON2, False),
    ],
)
def test_include_same_祝日も実行する(day: date, expected: bool) -> None:
    assert matches(row(SAT_SUN, "include", "same"), day) is expected


@pytest.mark.parametrize(
    "day, expected",
    [
        (SUN1, True),  # 翌日 月
        (MON2, True),  # 翌日 火は祝日だが、none は祝日を見ない。火は指定内
        (THU5, True),  # 翌日 金
        (FRI6, False),  # 翌日 土（指定外）
        (SAT7, False),  # 翌日 日（指定外）
    ],
)
def test_none_before_翌日が指定した曜日(day: date, expected: bool) -> None:
    assert matches(row(MON_FRI, "none", "before"), day) is expected


@pytest.mark.parametrize(
    "day, expected",
    [
        (SUN1, True),  # 翌日 月（平日・祝日でない）
        (MON2, False),  # 翌日 火は祝日 → 除く
        (TUE3, True),  # 翌日 水
        (THU5, True),  # 翌日 金
        (FRI6, False),  # 翌日 土（指定外）
        (SAT7, False),  # 翌日 日（指定外）
    ],
)
def test_exclude_before_翌日が祝日でない指定曜日(day: date, expected: bool) -> None:
    assert matches(row(MON_FRI, "exclude", "before"), day) is expected


@pytest.mark.parametrize(
    "day, expected",
    [
        (MON2, True),  # 翌日 火は祝日
        (FRI6, True),  # 翌日 土
        (SAT7, True),  # 翌日 日
        (SUN1, False),  # 翌日 月（指定外）
        (TUE3, False),  # 翌日 水（指定外）
    ],
)
def test_include_before_翌日が祝日か指定曜日(day: date, expected: bool) -> None:
    assert matches(row(SAT_SUN, "include", "before"), day) is expected


@pytest.mark.parametrize(
    "day, expected",
    [
        (TUE3, True),  # 前日 月
        (WED4, True),  # 前日 火は祝日だが、none は祝日を見ない。火は指定内
        (SAT7, True),  # 前日 金
        (SUN8, False),  # 前日 土（指定外）
        (MON9, False),  # 前日 日（指定外）
    ],
)
def test_none_after_前日が指定した曜日(day: date, expected: bool) -> None:
    assert matches(row(MON_FRI, "none", "after"), day) is expected


@pytest.mark.parametrize(
    "day, expected",
    [
        (TUE3, True),  # 前日 月
        (WED4, False),  # 前日 火は祝日 → 除く
        (THU5, True),  # 前日 水
        (SAT7, True),  # 前日 金
        (SUN8, False),  # 前日 土（指定外）
    ],
)
def test_exclude_after_前日が祝日でない指定曜日(day: date, expected: bool) -> None:
    assert matches(row(MON_FRI, "exclude", "after"), day) is expected


@pytest.mark.parametrize(
    "day, expected",
    [
        (WED4, True),  # 前日 火は祝日
        (SUN8, True),  # 前日 土
        (MON9, True),  # 前日 日
        (TUE3, False),  # 前日 月（指定外）
        (THU5, False),  # 前日 水（指定外）
    ],
)
def test_include_after_前日が祝日か指定曜日(day: date, expected: bool) -> None:
    assert matches(row(SAT_SUN, "include", "after"), day) is expected


@pytest.mark.parametrize("mode", ["none", "include", "exclude"])
def test_前の日_次の日は_当日の判定を日付をずらして行うのと同じ(mode: str) -> None:
    """全日付で、before(r) = same(r+1)、after(r) = same(r-1) になる。"""
    for weekdays in (MON_FRI, SAT_SUN, (1,), (7,), (2, 4)):
        same, before, after = (row(weekdays, mode, shift) for shift in ("same", "before", "after"))
        day = date(2026, 1, 1)
        while day <= date(2026, 12, 31):  # 祝日・振替休日を含む 1 年分
            assert matches(before, day) is matches(same, day + timedelta(days=1)), (mode, weekdays, day)
            assert matches(after, day) is matches(same, day - timedelta(days=1)), (mode, weekdays, day)
            day += timedelta(days=1)


def test_実行日そのものは曜日や祝日で絞らない() -> None:
    # 「水曜日の前の日」は、火曜日に実行する。火曜日が指定の曜日（水）でなくても、祝日でも、実行する
    assert matches(row((3,), "none", "before"), TUE3) is True
    assert matches(row((3,), "exclude", "before"), TUE3) is True  # 基準日（水）が祝日でなければ実行する
    assert matches(row((3,), "none", "before"), MON2) is False  # 月曜日の翌日は火曜日（指定外）


def test_振替休日も祝日として扱う() -> None:
    # 2026-05-06（水）は憲法記念日の振替休日
    substitute = date(2026, 5, 6)
    assert matches(row(SAT_SUN, "include", "same"), substitute) is True
    assert matches(row(MON_FRI, "exclude", "same"), substitute) is False
    assert matches(row(MON_FRI, "exclude", "before"), date(2026, 5, 5)) is False  # 翌日が振替休日


def test_毎日は祝日の扱いと実行日の取り方に関わらず常に実行する() -> None:
    for day in (MON2, TUE3, SAT7, SUN8):
        assert matches(row((), condition="daily"), day) is True


def test_理由に基準日が示される() -> None:
    ok, reason = runner_service._condition_matches(row(MON_FRI, "exclude", "before"), MON2)
    assert ok is False
    assert "基準日でない" in reason
    assert "2026-11-03" in reason and "祝日" in reason  # 基準日（翌日）の日付と、祝日であること
    assert "祝日の扱い=exclude" in reason and "実行日の取り方=before" in reason


# ---- 時刻の窓との組み合わせ（select_due） ----


def test_実行日は予定の日付で決まり_日付をまたぐ起動の遅れでも基準日は予定の日付から求める() -> None:
    # 23:58 の予定を、翌日 0:02 の起動で処理する。予定の日付は 11/2（月）。「の前の日」の基準日は 11/3（火・祝日）
    schedule = row(MON_FRI, "exclude", "before")
    schedule = RoomScheduleRow(**{**schedule.__dict__, "run_time": time(23, 58)})
    due, skipped = select_due([schedule], at(TUE3, 0, 2), grace_minutes=5)
    assert due == []
    assert skipped and "基準日でない" in skipped[0].reason

    ok = RoomScheduleRow(**{**schedule.__dict__, "holiday_mode": "none"})  # 祝日を見なければ、火曜は指定内
    due, _ = select_due([ok], at(TUE3, 0, 2), grace_minutes=5)
    assert [d.run_date for d in due] == [MON2]


# ---- ジョブ全体（一括切替の定期実行を含む） ----


def test_曜日の指定と祝日を除くと前の日で_ジョブが基準日どおりに実行する(
    switchbot: FakeSwitchBot, user_id: int, log_dir: Path
) -> None:
    s = make(user_id, condition="weekdays", weekdays=MON_FRI, holiday_mode="exclude", day_shift="before")

    on_holiday_eve = run_once(now=at(MON2, 7, 1), schedules=[s])  # 翌日が祝日
    assert on_holiday_eve[0].outcome is None
    assert "基準日でない" in (on_holiday_eve[0].reason or "")
    assert switchbot.commands == []
    assert last_run(s.id).last_run_at is None

    on_sunday = run_once(now=at(SUN1, 7, 1), schedules=[s])  # 翌日が月曜
    assert on_sunday[0].outcome == "success"
    assert on_sunday[0].run_date == SUN1
    log = (log_dir / LOG_FILE).read_text(encoding="utf-8")
    assert "祝日の扱い=exclude 実行日の取り方=before" in log
    assert "実行日=2026-11-01 基準日=2026-11-02" in log


def test_一括切替の定期実行も従来どおり動く(switchbot: FakeSwitchBot, user_id: int) -> None:
    s = make(user_id, scene="out")
    reports = run_once(now=at(THU5, 7, 0, 30), schedules=[s])
    assert reports[0].outcome == "success"
    assert set(switchbot.commands) == {(ID_INDOOR, "turnOff"), (ID_BEDSIDE, "turnOff"), (ID_INDIRECT, "turnOff")}


# ---- 機器の個別切替 ----


@pytest.mark.parametrize(
    "device, state, expected",
    [
        ("indirect_light", "on", (ID_INDIRECT, "turnOn")),
        ("indirect_light", "off", (ID_INDIRECT, "turnOff")),
        ("indoor_speaker", "on", (ID_INDOOR, "turnOn")),
        ("indoor_speaker", "off", (ID_INDOOR, "turnOff")),
        ("bedside_speaker", "on", (ID_BEDSIDE, "turnOn")),
        ("bedside_speaker", "off", (ID_BEDSIDE, "turnOff")),
    ],
)
def test_個別切替は指定した機器だけに1回指示する(
    switchbot: FakeSwitchBot, user_id: int, device: str, state: str, expected: tuple[str, str]
) -> None:
    s = make(user_id, device=device, state=state)

    reports = run_once(now=at(THU5, 7, 0, 30), schedules=[s])

    assert reports[0].outcome == "success"
    assert switchbot.commands == [expected]  # 他の機器へは指示しない。玄関ドアにも触れない
    assert all(device_id != ID_DOOR for device_id, _ in switchbot.commands)
    assert switchbot.status_calls == []  # 反映待ちの取り直しをしない
    row_ = last_run(s.id)
    assert row_.last_run_result == "success"
    assert row_.last_run_at is not None
    assert row_.last_failed_devices == ()


@pytest.mark.parametrize("state", ["on", "off"])
def test_電灯の個別切替は指示せず成功になる(
    switchbot: FakeSwitchBot, user_id: int, state: str, log_dir: Path
) -> None:
    s = make(user_id, device="ceiling_light", state=state)

    reports = run_once(now=at(THU5, 7, 0, 30), schedules=[s])

    assert reports[0].outcome == "success"
    assert switchbot.commands == []
    assert last_run(s.id).last_run_result == "success"
    assert last_run(s.id).last_failed_devices == ()
    assert "未実装のため何も指示しない" in (log_dir / LOG_FILE).read_text(encoding="utf-8")


def test_個別切替の失敗はfailureと失敗した機器1つが記録される(
    switchbot: FakeSwitchBot, user_id: int, log_dir: Path
) -> None:
    switchbot.command_errors[ID_BEDSIDE] = failure()
    s = make(user_id, device="bedside_speaker", state="on")

    reports = run_once(now=at(THU5, 7, 0, 30), schedules=[s])

    assert reports[0].outcome == "failure"
    row_ = last_run(s.id)
    assert row_.last_run_result == "failure"  # partial にはならない
    assert row_.last_failed_devices == ("bedside_speaker",)
    log = (log_dir / LOG_FILE).read_text(encoding="utf-8")
    assert "結果=failure" in log
    assert "action=device device=bedside_speaker state=on" in log


def test_個別切替の失敗でも他の定期実行は続く(switchbot: FakeSwitchBot, user_id: int) -> None:
    switchbot.command_errors[ID_INDOOR] = failure()
    failing = make(user_id, device="indoor_speaker", state="on")
    healthy = make(user_id, device="indirect_light", state="off")

    reports = {r.schedule_id: r for r in run_once(now=at(THU5, 7, 0, 30), schedules=[failing, healthy])}

    assert reports[failing.id].outcome == "failure"
    assert reports[healthy.id].outcome == "success"
    assert (ID_INDIRECT, "turnOff") in switchbot.commands


def test_個別切替も同じ日に重ねて実行しない(switchbot: FakeSwitchBot, user_id: int) -> None:
    s = make(user_id, device="indirect_light", state="off")
    assert run_once(now=at(THU5, 7, 0, 30), schedules=[s])[0].outcome == "success"
    again = run_once(now=at(THU5, 7, 1, 30), schedules=[s])
    assert again[0].outcome is None and again[0].reason == "実行済み"
    assert switchbot.commands == [(ID_INDIRECT, "turnOff")]


def test_個別切替でも祝日の扱いと実行日の取り方が効く(switchbot: FakeSwitchBot, user_id: int) -> None:
    s = make(
        user_id,
        condition="weekdays",
        weekdays=MON_FRI,
        holiday_mode="exclude",
        day_shift="before",
        device="indirect_light",
        state="off",
    )
    assert run_once(now=at(MON2, 7, 1), schedules=[s])[0].outcome is None  # 翌日が祝日
    assert run_once(now=at(SUN1, 7, 1), schedules=[s])[0].outcome == "success"
    assert switchbot.commands == [(ID_INDIRECT, "turnOff")]


def test_無効な個別切替は実行しない(switchbot: FakeSwitchBot, user_id: int) -> None:
    s = make(user_id, device="indirect_light", state="off", enabled=False)
    assert run_once(now=at(THU5, 7, 0, 30), schedules=[s])[0].reason == "無効"
    assert switchbot.commands == []


def test_SwitchBotの設定が未完了なら個別切替は失敗として記録する(
    monkeypatch: pytest.MonkeyPatch, user_id: int
) -> None:
    from app.services import device_service

    monkeypatch.setattr(device_service, "build_client", lambda cfg: None)
    s = make(user_id, device="indirect_light", state="off")
    reports = run_once(now=at(THU5, 7, 0, 30), schedules=[s])
    assert reports[0].outcome == "failure"
    assert last_run(s.id).last_failed_devices == ("indirect_light",)
