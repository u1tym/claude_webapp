from __future__ import annotations

import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import repos
from app.config import load_config
from app.db import get_conn
from app.jobs.__main__ import main as job_main
from app.logger import LOG_FILE
from app.repos import RoomScheduleRow
from app.services import holiday_service, runner_service, scene_service
from app.services.runner_service import run_once, select_due
from app.timeutil import JST
from fakes import (
    ID_BEDSIDE,
    ID_CEILING,
    ID_DOOR,
    ID_INDIRECT,
    ID_INDOOR,
    TEST_SECRET,
    TEST_TOKEN,
    FakeSwitchBot,
    failure,
)
from helpers import insert_user, unique

# 2026-10-01 は木曜日（isoweekday = 4）、祝日ではない
THU = date(2026, 10, 1)
# 2026-11-03 は文化の日（火曜日）
CULTURE_DAY = date(2026, 11, 3)


def at(day: date, hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=JST)


def _log_text(log_dir: Path) -> str:
    return (log_dir / LOG_FILE).read_text(encoding="utf-8")


@pytest.fixture
def user_id() -> Iterator[int]:
    uid = insert_user(unique("room_runner"))
    yield uid
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM room.room_schedules WHERE created_by_user_id = %s", (uid,))


def make(
    user_id: int,
    condition: str = "daily",
    run_time: str = "07:00",
    scene: str = "indoor_speaker",
    weekdays: tuple[int, ...] = (),
    enabled: bool = True,
    holiday_mode: str = "none",
    day_shift: str = "same",
    device: str | None = None,
    state: str | None = None,
    pattern: str | None = None,
) -> RoomScheduleRow:
    from datetime import time

    hour, minute = (int(x) for x in run_time.split(":"))
    definition = repos.ScheduleDefinition(
        condition_type=condition,
        weekdays=weekdays,
        holiday_mode=holiday_mode,
        day_shift=day_shift,
        run_time=time(hour, minute),
        action_type="scene" if device is None else "device",
        scene=None if device is not None else scene,
        device=device,
        target_state=state,
        dimming_pattern=pattern,
    )
    schedule_id = repos.insert_room_schedule(user_id, definition, enabled)
    row = repos.get_room_schedule(schedule_id)
    assert row is not None
    return row


def last_run(schedule_id: int) -> RoomScheduleRow:
    row = repos.get_room_schedule(schedule_id)
    assert row is not None
    return row


# ---- 祝日の判定 ----


def test_祝日は振替休日を含めて判定する() -> None:
    assert holiday_service.is_holiday(CULTURE_DAY)  # 文化の日
    assert holiday_service.is_holiday(date(2026, 5, 6))  # 憲法記念日の振替休日
    assert not holiday_service.is_holiday(THU)
    assert not holiday_service.is_holiday(date(2026, 10, 3))  # 土曜日（祝日ではない）


# ---- 実行条件と時刻の判定 ----


def test_毎日の定期実行は指定時刻に1回実行され最終実行が更新される(
    switchbot: FakeSwitchBot, user_id: int, log_dir: Path
) -> None:
    s = make(user_id)

    reports = run_once(now=at(THU, 7, 0, 30), schedules=[s])

    assert [(r.schedule_id, r.run_date, r.outcome) for r in reports] == [(s.id, THU, "success")]
    assert set(switchbot.commands) == {(ID_INDOOR, "turnOn"), (ID_BEDSIDE, "turnOff")}
    row = last_run(s.id)
    assert row.last_run_result == "success"
    assert row.last_run_at is not None
    assert row.last_failed_devices == ()
    log = _log_text(log_dir)
    assert "定期実行の判定開始" in log
    assert f"id={s.id} 判断=実行する" in log
    assert "主体=定期実行" in log  # 一括切替の記録の主体が定期実行


def test_指定時刻より前は実行しない(switchbot: FakeSwitchBot, user_id: int) -> None:
    s = make(user_id)
    reports = run_once(now=at(THU, 6, 59, 59), schedules=[s])
    assert reports[0].outcome is None
    assert reports[0].reason == "時刻が範囲外"
    assert switchbot.commands == []
    assert last_run(s.id).last_run_at is None


@pytest.mark.parametrize(
    "now, runs",
    [
        (at(THU, 7, 0, 0), True),  # ちょうど
        (at(THU, 7, 4, 59), True),  # 猶予内
        (at(THU, 7, 5, 0), True),  # 猶予ちょうど
        (at(THU, 7, 5, 1), False),  # 猶予を超えた
    ],
)
def test_起動の遅れは猶予内なら実行する(
    switchbot: FakeSwitchBot, user_id: int, now: datetime, runs: bool
) -> None:
    s = make(user_id)
    reports = run_once(now=now, schedules=[s], grace_minutes=5)
    assert (reports[0].outcome is not None) is runs
    assert bool(switchbot.commands) is runs


def test_猶予分は設定から読む(switchbot: FakeSwitchBot, user_id: int) -> None:
    s = make(user_id)
    assert load_config().schedule_grace_minutes == 5
    # 7:05:30 は既定の猶予 5 分を超えるので実行しない
    assert run_once(now=at(THU, 7, 5, 30), schedules=[s])[0].outcome is None
    # 猶予を 10 分にすれば実行する
    assert run_once(now=at(THU, 7, 5, 30), schedules=[s], grace_minutes=10)[0].outcome == "success"


def test_曜日の指定は指定した曜日だけ実行する(switchbot: FakeSwitchBot, user_id: int) -> None:
    thursday = make(user_id, condition="weekdays", weekdays=(4,))
    monday_tuesday = make(user_id, condition="weekdays", weekdays=(1, 2), scene="out")

    reports = {
        r.schedule_id: r
        for r in run_once(now=at(THU, 7, 1), schedules=[thursday, monday_tuesday])
    }

    assert reports[thursday.id].outcome == "success"
    assert reports[monday_tuesday.id].outcome is None
    assert "基準日でない" in (reports[monday_tuesday.id].reason or "")
    assert last_run(monday_tuesday.id).last_run_at is None


def test_日本標準時で判定する(switchbot: FakeSwitchBot, user_id: int) -> None:
    s = make(user_id)
    # UTC の 2026-09-30 22:00:30 は日本標準時の 2026-10-01 07:00:30
    now_utc = datetime(2026, 9, 30, 22, 0, 30, tzinfo=timezone.utc)
    reports = run_once(now=now_utc, schedules=[s])
    assert reports[0].run_date == THU
    assert reports[0].outcome == "success"


def test_無効な定期実行は実行しない(switchbot: FakeSwitchBot, user_id: int) -> None:
    s = make(user_id, enabled=False)
    reports = run_once(now=at(THU, 7, 0, 30), schedules=[s])
    assert reports[0].outcome is None
    assert reports[0].reason == "無効"
    assert switchbot.commands == []


def test_有効なものだけをDBから読む(user_id: int) -> None:
    on = make(user_id, run_time="01:00")
    off = make(user_id, run_time="01:01", enabled=False)
    ids = [r.id for r in repos.list_room_schedules(only_enabled=True)]
    assert on.id in ids
    assert off.id not in ids


def test_日付をまたぐ起動の遅れは予定の日付で実行する(
    switchbot: FakeSwitchBot, user_id: int
) -> None:
    s = make(user_id, run_time="23:58")
    now = at(THU + timedelta(days=1), 0, 1)  # 翌日 0:01 に起動

    first = run_once(now=now, schedules=[s])
    assert first[0].run_date == THU  # 予定の日付（前日）
    assert first[0].outcome == "success"
    assert len(switchbot.commands) == 2

    # 同じ判定をもう一度行っても、実行しない
    second = run_once(now=now, schedules=[s])
    assert second[0].outcome is None
    assert second[0].reason == "実行済み"
    assert len(switchbot.commands) == 2


def test_日付をまたぐときの曜日は予定の日付で判定する(
    switchbot: FakeSwitchBot, user_id: int
) -> None:
    thursday = make(user_id, condition="weekdays", weekdays=(4,), run_time="23:58")
    friday = make(user_id, condition="weekdays", weekdays=(5,), run_time="23:58", scene="out")
    now = at(THU + timedelta(days=1), 0, 1)  # 金曜 0:01、予定は木曜 23:58

    reports = {r.schedule_id: r for r in run_once(now=now, schedules=[thursday, friday])}

    assert reports[thursday.id].outcome == "success"
    assert reports[friday.id].outcome is None


# ---- 重複実行の防止 ----


def test_同じ日の同じ定期実行は1回だけ実行する(
    switchbot: FakeSwitchBot, user_id: int, log_dir: Path
) -> None:
    s = make(user_id)

    first = run_once(now=at(THU, 7, 0, 10), schedules=[s])
    second = run_once(now=at(THU, 7, 1, 10), schedules=[s])

    assert first[0].outcome == "success"
    assert second[0].outcome is None
    assert second[0].reason == "実行済み"
    assert len(switchbot.commands) == 2  # 1 回分だけ
    assert "理由=実行済み" in _log_text(log_dir)


def test_別の日なら再び実行する(switchbot: FakeSwitchBot, user_id: int) -> None:
    s = make(user_id)
    run_once(now=at(THU, 7, 0, 10), schedules=[s])
    next_day = run_once(now=at(THU + timedelta(days=1), 7, 0, 10), schedules=[s])
    assert next_day[0].outcome == "success"
    assert len(switchbot.commands) == 4


def test_2つのジョブが同時に動いても1回だけ実行する(
    switchbot: FakeSwitchBot, user_id: int
) -> None:
    s = make(user_id)
    barrier = threading.Barrier(4)

    def job() -> list[runner_service.RunReport]:
        barrier.wait()
        return run_once(now=at(THU, 7, 0, 10), schedules=[s])

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = [f.result() for f in [pool.submit(job) for _ in range(4)]]

    executed = [r for reports in results for r in reports if r.outcome is not None]
    assert len(executed) == 1
    assert len(switchbot.commands) == 2  # 一括切替は 1 回分だけ


# ---- 失敗しても続ける ----


def test_ある定期実行が失敗しても他の定期実行は続く(
    switchbot: FakeSwitchBot, user_id: int
) -> None:
    switchbot.command_errors[ID_INDOOR] = failure()
    switchbot.command_errors[ID_BEDSIDE] = failure()
    failing = make(user_id, scene="indoor_speaker", run_time="07:00")
    healthy = make(user_id, scene="out", run_time="07:00")

    reports = {r.schedule_id: r for r in run_once(now=at(THU, 7, 0, 30), schedules=[failing, healthy])}

    # out も屋内・枕元スピーカーを切る対象なので、一部失敗になる。いずれも最後まで処理される
    assert reports[failing.id].outcome == "failure"
    assert reports[healthy.id].outcome == "partial"
    assert last_run(failing.id).last_run_result == "failure"
    assert set(last_run(failing.id).last_failed_devices) == {"indoor_speaker", "bedside_speaker"}
    row = last_run(healthy.id)
    assert row.last_run_result == "partial"
    assert set(row.last_failed_devices) == {"indoor_speaker", "bedside_speaker"}


def test_一部失敗は失敗した機器を記録する(switchbot: FakeSwitchBot, user_id: int, log_dir: Path) -> None:
    switchbot.command_errors[ID_BEDSIDE] = failure()
    s = make(user_id, scene="indoor_speaker")

    reports = run_once(now=at(THU, 7, 0, 30), schedules=[s])

    assert reports[0].outcome == "partial"
    row = last_run(s.id)
    assert row.last_run_result == "partial"
    assert row.last_failed_devices == ("bedside_speaker",)
    # 成功した屋内スピーカーは元に戻さない
    assert switchbot.commands.count((ID_INDOOR, "turnOn")) == 1
    assert "結果=partial" in _log_text(log_dir)


def test_電灯選択の定期実行は_既定のパターンで電灯を点灯し_間接照明を消す(switchbot: FakeSwitchBot, user_id: int) -> None:
    s = make(user_id, scene="ceiling_light")
    reports = run_once(now=at(THU, 7, 0, 30), schedules=[s])
    assert reports[0].outcome == "success"
    assert set(switchbot.commands) == {
        (ID_CEILING, "turnOn"),
        (ID_CEILING, "setBrightness"),
        (ID_CEILING, "setColorTemperature"),
        (ID_INDIRECT, "turnOff"),
    }
    assert [p for d, c, p in switchbot.calls if d == ID_CEILING and c == "setBrightness"] == ["100"]
    assert last_run(s.id).last_failed_devices == ()


def test_電灯選択の定期実行で電灯が失敗したら_失敗した機器に電灯が残る(switchbot: FakeSwitchBot, user_id: int) -> None:
    switchbot.step_errors[(ID_CEILING, "turnOn")] = failure()
    s = make(user_id, scene="ceiling_light")
    reports = run_once(now=at(THU, 7, 0, 30), schedules=[s])
    assert reports[0].outcome == "partial"
    assert last_run(s.id).last_failed_devices == ("ceiling_light",)


def test_想定外の例外でも失敗として記録し次へ進む(
    switchbot: FakeSwitchBot, user_id: int, monkeypatch: pytest.MonkeyPatch, log_dir: Path
) -> None:
    first = make(user_id, scene="out", run_time="07:00")
    second = make(user_id, scene="indoor_speaker", run_time="07:00")
    original = scene_service.run_scene

    def flaky(scene: str, *args: object, **kwargs: object) -> object:
        if scene == "out":
            raise RuntimeError("boom " + ID_INDIRECT)
        return original(scene, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(scene_service, "run_scene", flaky)

    reports = {r.schedule_id: r for r in run_once(now=at(THU, 7, 0, 30), schedules=[first, second])}

    assert reports[first.id].outcome == "failure"
    assert reports[second.id].outcome == "success"
    assert last_run(first.id).last_run_result == "failure"
    assert last_run(first.id).last_failed_devices == (
        "ceiling_light",
        "indirect_light",
        "indoor_speaker",
        "bedside_speaker",
    )
    log = _log_text(log_dir)
    assert "RuntimeError" in log
    assert ID_INDIRECT not in log  # 例外の内容（機器の識別子）はログに出さない


def test_SwitchBotの設定が未完了なら失敗として記録する(
    switchbot: FakeSwitchBot, user_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import device_service

    monkeypatch.setattr(device_service, "build_client", lambda _cfg=None: None)
    s = make(user_id)
    reports = run_once(now=at(THU, 7, 0, 30), schedules=[s])
    assert reports[0].outcome == "failure"
    assert last_run(s.id).last_run_result == "failure"


# ---- 定義の更新は最終実行を変えない／ログ ----


def test_最終実行の更新は定義の項目を変えない(switchbot: FakeSwitchBot, user_id: int) -> None:
    s = make(user_id, condition="weekdays", weekdays=(4, 5), run_time="07:00", scene="out")
    run_once(now=at(THU, 7, 0, 30), schedules=[s])
    row = last_run(s.id)
    assert (row.condition_type, row.weekdays, row.run_time, row.scene, row.is_enabled) == (
        s.condition_type,
        s.weekdays,
        s.run_time,
        s.scene,
        s.is_enabled,
    )


def test_判定の結果が全件ログに残り秘密情報は出ない(
    switchbot: FakeSwitchBot, user_id: int, log_dir: Path
) -> None:
    ran = make(user_id, run_time="07:00")
    wrong_day = make(user_id, condition="weekdays", weekdays=(1,), run_time="07:00")
    off = make(user_id, run_time="07:00", enabled=False)
    later = make(user_id, run_time="12:00")

    run_once(now=at(THU, 7, 0, 30), schedules=[ran, wrong_day, off, later])

    log = _log_text(log_dir)
    assert f"id={ran.id} 判断=実行する" in log
    assert f"id={wrong_day.id} 判断=実行しない 理由=基準日でない" in log
    assert f"id={off.id} 判断=実行しない 理由=無効" in log
    assert f"id={later.id} 判断=実行しない 理由=時刻が範囲外" in log
    assert "定期実行の判定終了 実行=1 実行しない=3" in log
    for secret in (ID_INDIRECT, ID_INDOOR, ID_BEDSIDE, ID_DOOR, TEST_TOKEN, TEST_SECRET):
        assert secret not in log


# ---- ジョブの入口 ----


def test_ジョブは1回判定して0で終わりログの出力元はjob(
    monkeypatch: pytest.MonkeyPatch, log_dir: Path
) -> None:
    calls: list[int] = []
    monkeypatch.setattr(runner_service, "run_once", lambda: calls.append(1) or [])
    # ログの出力先を、テストの一時フォルダのままにする
    monkeypatch.setattr("app.jobs.__main__.setup_logging", lambda: None)

    assert job_main() == 0
    assert calls == [1]
    from app.logger import write

    write("INF", "確認")
    assert " INF [job] 確認" in _log_text(log_dir)


def test_ジョブの想定外の失敗は1を返しログに残す(
    monkeypatch: pytest.MonkeyPatch, log_dir: Path
) -> None:
    def boom() -> list[runner_service.RunReport]:
        raise RuntimeError("secret detail")

    monkeypatch.setattr(runner_service, "run_once", boom)
    monkeypatch.setattr("app.jobs.__main__.setup_logging", lambda: None)

    assert job_main() == 1
    log = _log_text(log_dir)
    assert "定期実行ジョブの失敗 理由=RuntimeError" in log
    assert "secret detail" not in log


# ---- 判定だけの確認 ----


def _row(**override: object) -> RoomScheduleRow:
    from datetime import time

    values: dict[str, object] = {
        "id": 1,
        "created_by_user_id": 1,
        "condition_type": "daily",
        "weekdays": (),
        "holiday_mode": "none",
        "day_shift": "same",
        "run_time": time(7, 0),
        "action_type": "scene",
        "scene": "out",
        "device": None,
        "target_state": None,
        "is_enabled": True,
        "last_run_at": None,
        "last_run_result": None,
        "last_failed_devices": (),
    }
    values.update(override)
    return RoomScheduleRow(**values)  # type: ignore[arg-type]


def test_select_dueは複数日にまたがる猶予でも予定の日付で選ぶ() -> None:
    # 猶予 2000 分（約 33 時間）なら、8:00 の判定で、昨日 7:00 と今日 7:00 が範囲に入る
    due, _ = select_due([_row()], at(THU, 8, 0), grace_minutes=2000)
    assert sorted(d.run_date for d in due) == [THU - timedelta(days=1), THU]


def test_select_dueは毎日の定期実行を条件で落とさない() -> None:
    due, skipped = select_due([_row()], at(THU, 7, 0, 1), grace_minutes=5)
    assert [d.run_date for d in due] == [THU]
    assert skipped == []


def test_is_holiday_includes_user_holiday(monkeypatch) -> None:
    from app import repos

    calls: list[tuple[int, date]] = []

    def fake(user_id: int, day: date) -> bool:
        calls.append((user_id, day))
        return user_id == 7 and day == THU

    monkeypatch.setattr(holiday_service, "is_user_holiday", fake)
    assert holiday_service.is_holiday(THU, 7) is True
    assert holiday_service.is_holiday(THU, 8) is False
    assert holiday_service.is_holiday(THU) is False
    assert holiday_service.is_holiday(CULTURE_DAY, 8) is True  # 日本の祝日は DB を見ない
    assert (8, CULTURE_DAY) not in calls
    assert repos.is_user_holiday is not None
