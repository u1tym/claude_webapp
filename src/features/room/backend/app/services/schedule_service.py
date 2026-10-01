from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import time
from typing import Any

from app import repos
from app.errors import InvalidInputError, NotFoundError
from app.logger import write
from app.repos import RoomScheduleRow
from app.timeutil import iso_seconds

CONDITIONS = ("daily", "weekdays", "holiday")
SCENES = ("indoor_speaker", "bedside_speaker", "ceiling_light", "indirect_light", "out")

# 時刻は HH:MM（00:00〜23:59）。秒は受け付けない
_RUN_TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
# bigint の上限。これを超える識別子は存在しない扱いにする
_MAX_ID = 2**63 - 1


@dataclass(frozen=True)
class ScheduleInput:
    """登録・変更の入力（検証前）。"""

    condition: object
    weekdays: object
    run_time: object
    scene: object
    is_enabled: object


@dataclass(frozen=True)
class ValidScheduleInput:
    condition: str
    weekdays: tuple[int, ...]
    run_time: time
    scene: str
    is_enabled: bool | None


def validate(data: ScheduleInput) -> ValidScheduleInput:
    """入力を検証する。不正なら InvalidInputError。"""
    reasons: list[str] = []

    condition = data.condition
    if condition not in CONDITIONS:
        reasons.append("実行条件が不正")

    weekdays_raw = data.weekdays
    weekdays: tuple[int, ...] = ()
    if weekdays_raw is not None:
        if not isinstance(weekdays_raw, (list, tuple)) or any(
            isinstance(d, bool) or not isinstance(d, int) or not 1 <= d <= 7 for d in weekdays_raw
        ):
            reasons.append("曜日が不正")
        elif len(set(weekdays_raw)) != len(weekdays_raw):
            reasons.append("曜日が重複")
        else:
            weekdays = tuple(sorted(weekdays_raw))
    if condition == "weekdays" and not weekdays and "曜日が不正" not in reasons:
        reasons.append("曜日の指定なのに曜日がない")
    if condition in ("daily", "holiday") and weekdays:
        reasons.append("曜日の指定でないのに曜日がある")

    run_time: time | None = None
    if isinstance(data.run_time, str):
        match = _RUN_TIME.match(data.run_time)
        if match:
            run_time = time(int(match.group(1)), int(match.group(2)))
    if run_time is None:
        reasons.append("時刻の形式が不正")

    if data.scene not in SCENES:
        reasons.append("一括切替が不正")

    is_enabled = data.is_enabled
    if is_enabled is not None and not isinstance(is_enabled, bool):
        reasons.append("有効／無効が不正")

    if reasons:
        write("WRN", f"定期実行の入力不正 理由={'、'.join(reasons)}")
        raise InvalidInputError()
    assert run_time is not None
    return ValidScheduleInput(
        condition=str(condition),
        weekdays=weekdays,
        run_time=run_time,
        scene=str(data.scene),
        is_enabled=is_enabled if isinstance(is_enabled, bool) else None,
    )


def to_api(row: RoomScheduleRow) -> dict[str, Any]:
    """API の応答の 1 件分にする。"""
    last_run: dict[str, Any] | None = None
    if row.last_run_at is not None and row.last_run_result is not None:
        last_run = {
            "at": iso_seconds(row.last_run_at),
            "result": row.last_run_result,
            "failed_devices": list(row.last_failed_devices),
        }
    return {
        "id": row.id,
        "condition": row.condition_type,
        "weekdays": list(row.weekdays),
        "run_time": row.run_time.strftime("%H:%M"),
        "scene": row.scene,
        "is_enabled": row.is_enabled,
        "last_run": last_run,
    }


def _check_id(schedule_id: int) -> None:
    if not 1 <= schedule_id <= _MAX_ID:
        write("WRN", f"定期実行の対象なし id={schedule_id}")
        raise NotFoundError()


def _describe(data: ValidScheduleInput) -> str:
    return (
        f"condition={data.condition} weekdays={list(data.weekdays)} "
        f"run_time={data.run_time.strftime('%H:%M')} scene={data.scene} is_enabled={data.is_enabled}"
    )


def list_schedules() -> list[dict[str, Any]]:
    rows = repos.list_room_schedules()
    write("INF", f"定期実行の一覧取得 件数={len(rows)}")
    return [to_api(row) for row in rows]


def create_schedule(data: ScheduleInput, user_id: int, username: str = "") -> dict[str, Any]:
    valid = validate(data)
    write("INF", f"定期実行の登録要求 username={username} {_describe(valid)}")
    enabled = True if valid.is_enabled is None else valid.is_enabled
    schedule_id = repos.insert_room_schedule(
        user_id, valid.condition, valid.weekdays, valid.run_time, valid.scene, enabled
    )
    row = repos.get_room_schedule(schedule_id)
    assert row is not None
    write("INF", f"定期実行の登録成功 id={schedule_id}")
    return to_api(row)


def update_schedule(
    schedule_id: int, data: ScheduleInput, username: str = ""
) -> dict[str, Any]:
    _check_id(schedule_id)
    valid = validate(data)
    write("INF", f"定期実行の変更要求 id={schedule_id} username={username} {_describe(valid)}")
    updated = repos.update_room_schedule(
        schedule_id,
        valid.condition,
        valid.weekdays,
        valid.run_time,
        valid.scene,
        valid.is_enabled,
    )
    if not updated:
        write("WRN", f"定期実行の変更失敗 id={schedule_id} 理由=対象なし")
        raise NotFoundError()
    row = repos.get_room_schedule(schedule_id)
    assert row is not None
    write("INF", f"定期実行の変更成功 id={schedule_id}")
    return to_api(row)


def set_enabled(schedule_id: int, is_enabled: object, username: str = "") -> dict[str, Any]:
    _check_id(schedule_id)
    if not isinstance(is_enabled, bool):
        write("WRN", f"定期実行の有効／無効の入力不正 id={schedule_id} 理由=真偽値でない")
        raise InvalidInputError()
    write("INF", f"定期実行の有効／無効の切替要求 id={schedule_id} username={username} is_enabled={is_enabled}")
    if not repos.set_room_schedule_enabled(schedule_id, is_enabled):
        write("WRN", f"定期実行の有効／無効の切替失敗 id={schedule_id} 理由=対象なし")
        raise NotFoundError()
    row = repos.get_room_schedule(schedule_id)
    assert row is not None
    write("INF", f"定期実行の有効／無効の切替成功 id={schedule_id} is_enabled={is_enabled}")
    return to_api(row)


def delete_schedule(schedule_id: int, username: str = "") -> None:
    _check_id(schedule_id)
    write("INF", f"定期実行の削除要求 id={schedule_id} username={username}")
    if not repos.delete_room_schedule(schedule_id):
        write("WRN", f"定期実行の削除失敗 id={schedule_id} 理由=対象なし")
        raise NotFoundError()
    write("INF", f"定期実行の削除成功 id={schedule_id}")
