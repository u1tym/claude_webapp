from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app import repos
from app.actors import ACTOR_JOB
from app.config import load_config
from app.logger import write
from app.repos import RoomScheduleRow
from app.services import holiday_service, scene_service
from app.services.scene_service import FAILURE, SUCCESS
from app.switchbot.client import SwitchBotApi
from app.timeutil import JST, now_jst

# 失敗した機器として記録できるのは、一括切替の対象になり得る 4 機器（玄関ドアは含まない）
_RECORDABLE_DEVICES = ("ceiling_light", "indirect_light", "indoor_speaker", "bedside_speaker")


@dataclass(frozen=True)
class DueSchedule:
    """今回の判定で実行すべき定期実行と、その実行日（予定の日付）。"""

    schedule: RoomScheduleRow
    run_date: date


@dataclass(frozen=True)
class Skipped:
    schedule: RoomScheduleRow
    reason: str


@dataclass(frozen=True)
class RunReport:
    """定期実行 1 件の判定の結果。outcome が None なら実行していない。"""

    schedule_id: int
    run_date: date | None
    outcome: str | None
    reason: str | None = None


def _condition_matches(schedule: RoomScheduleRow, day: date) -> tuple[bool, str]:
    """実行条件が、予定の日付に合うかと、合わないときの理由を返す。"""
    if schedule.condition_type == "daily":
        return True, ""
    if schedule.condition_type == "weekdays":
        if day.isoweekday() in schedule.weekdays:
            return True, ""
        return False, f"条件に合わない（曜日 {day.isoweekday()} は指定外）"
    if schedule.condition_type == "holiday":
        if holiday_service.is_holiday(day):
            return True, ""
        return False, "条件に合わない（祝日でない）"
    return False, "条件に合わない（実行条件が不明）"


def select_due(
    schedules: list[RoomScheduleRow], now: datetime, grace_minutes: int
) -> tuple[list[DueSchedule], list[Skipped]]:
    """判定時刻 now に実行すべき定期実行を選ぶ。

    指定時刻が、now の grace_minutes 分前から now までの範囲にあり、その予定の日付が
    実行条件に合うものを対象にする。日付をまたぐ起動の遅れは、予定の日付で判定する。
    """
    now = now.astimezone(JST)
    window_start = now - timedelta(minutes=grace_minutes)
    days: list[date] = []
    day = window_start.date()
    while day <= now.date():
        days.append(day)
        day += timedelta(days=1)

    due: list[DueSchedule] = []
    skipped: list[Skipped] = []
    for schedule in schedules:
        if not schedule.is_enabled:
            skipped.append(Skipped(schedule, "無効"))
            continue
        in_window = False
        reasons: list[str] = []
        for candidate in days:
            scheduled = datetime.combine(candidate, schedule.run_time, tzinfo=JST)
            if not window_start <= scheduled <= now:
                continue
            in_window = True
            matches, reason = _condition_matches(schedule, candidate)
            if matches:
                due.append(DueSchedule(schedule, candidate))
            else:
                reasons.append(reason)
        if not in_window:
            skipped.append(Skipped(schedule, "時刻が範囲外"))
        elif not any(d.schedule.id == schedule.id for d in due):
            skipped.append(Skipped(schedule, "、".join(reasons)))
    return due, skipped


def _execute(
    item: DueSchedule, client: SwitchBotApi | None
) -> tuple[str, tuple[str, ...]]:
    """一括切替を実行し、最終実行に残す結果と失敗した機器を返す。例外は失敗として扱う。"""
    schedule = item.schedule
    try:
        result = scene_service.run_scene(
            schedule.scene, actor=ACTOR_JOB, client=client, refetch=False
        )
    except Exception as exc:  # 想定外の失敗でも、他の定期実行は続ける
        write("ERR", f"定期実行の実行失敗 id={schedule.id} scene={schedule.scene} 理由={type(exc).__name__}")
        return FAILURE, tuple(
            device for device, _ in scene_service.SCENES.get(schedule.scene, ()) if device != "ceiling_light"
        )
    failed = tuple(
        r.device for r in result.results if r.outcome == FAILURE and r.device in _RECORDABLE_DEVICES
    )
    return result.outcome, failed


def run_once(
    now: datetime | None = None,
    client: SwitchBotApi | None = None,
    schedules: list[RoomScheduleRow] | None = None,
    grace_minutes: int | None = None,
) -> list[RunReport]:
    """1 回だけ判定して、実行すべき定期実行を実行する。"""
    current = (now or now_jst()).astimezone(JST)
    grace = grace_minutes if grace_minutes is not None else load_config().schedule_grace_minutes
    targets = schedules if schedules is not None else repos.list_room_schedules(only_enabled=True)
    write(
        "INF",
        f"定期実行の判定開始 判定時刻={current.strftime('%Y-%m-%d %H:%M:%S')} 猶予分={grace} 件数={len(targets)}",
    )

    due, skipped = select_due(targets, current, grace)
    reports: list[RunReport] = []
    for item in skipped:
        write("DBG", f"定期実行の判定 id={item.schedule.id} 判断=実行しない 理由={item.reason}")
        reports.append(RunReport(item.schedule.id, None, None, item.reason))

    for item in due:
        schedule = item.schedule
        try:
            # 実行の直前に記録を追加する。追加できたジョブだけが実行する（同時に動いても 1 回だけ）
            if not repos.insert_schedule_run(schedule.id, item.run_date):
                write(
                    "INF",
                    f"定期実行の判定 id={schedule.id} 判断=実行しない 理由=実行済み 実行日={item.run_date}",
                )
                reports.append(RunReport(schedule.id, item.run_date, None, "実行済み"))
                continue
            write(
                "INF",
                f"定期実行の判定 id={schedule.id} 判断=実行する scene={schedule.scene} "
                f"条件={schedule.condition_type} 時刻={schedule.run_time.strftime('%H:%M')} 実行日={item.run_date}",
            )
            outcome, failed = _execute(item, client)
            repos.update_last_run(schedule.id, now_jst(), outcome, failed)
            level = "INF" if outcome == SUCCESS else "WRN"
            write(
                level,
                f"定期実行の結果 id={schedule.id} scene={schedule.scene} 結果={outcome} 失敗した機器={list(failed)}",
            )
            reports.append(RunReport(schedule.id, item.run_date, outcome))
        except Exception as exc:  # DB の失敗など。他の定期実行は続ける
            write("ERR", f"定期実行の処理失敗 id={schedule.id} 理由={type(exc).__name__}")
            reports.append(RunReport(schedule.id, item.run_date, FAILURE, "処理失敗"))

    executed = sum(1 for r in reports if r.outcome is not None)
    write("INF", f"定期実行の判定終了 実行={executed} 実行しない={len(reports) - executed}")
    return reports
