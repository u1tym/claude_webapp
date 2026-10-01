"""切替のあとの、実機の反映待ち（取り直し）のテスト。

実機は、指示してから状態に反映されるまで、少し時間がかかる。指示の直後に取り直すと、
「状態が変わっていない」と誤って示されるため、間隔をおいて、目標の状態になるまで取り直す。
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import DEFAULT_SETTLE_SECONDS, load_config
from app.logger import LOG_FILE
from app.main import app as room_app
from app.services import device_service, runner_service
from app.services.device_service import SETTLE_INTERVAL_SECONDS, settle_step, switch_device
from app.services.scene_service import run_scene
from fakes import ID_BEDSIDE, ID_DOOR, ID_INDIRECT, ID_INDOOR, FakeSwitchBot, failure
from helpers import assign_feature, ensure_feature, insert_session, insert_user, unique



def _write_env(tmp_path: Path, body: str) -> Path:
    path = tmp_path / ".env"
    path.write_text(body, encoding="utf-8")
    return path


def set_limit(monkeypatch: pytest.MonkeyPatch, seconds: float) -> None:
    """反映待ちの上限を変える（テスト用の設定を、置き換える）。"""
    cfg = dataclasses.replace(device_service.load_config(), switch_settle_seconds=seconds)
    monkeypatch.setattr(device_service, "load_config", lambda: cfg)


def _log(log_dir: Path) -> str:
    return (log_dir / LOG_FILE).read_text(encoding="utf-8")


# ---- 設定値 ----


def test_上限の既定は5秒(tmp_path: Path) -> None:
    cfg = load_config(_write_env(tmp_path, ""))
    assert cfg.switch_settle_seconds == DEFAULT_SETTLE_SECONDS == 5.0
    assert cfg.warnings == ()


@pytest.mark.parametrize("raw, expected", [("0", 0.0), ("3", 3.0), ("2.5", 2.5), ("10", 10.0), (" 4 ", 4.0)])
def test_上限は0以上の数を読む(tmp_path: Path, raw: str, expected: float) -> None:
    cfg = load_config(_write_env(tmp_path, f"ROOM_SETTLE_SECONDS={raw}\n"))
    assert cfg.switch_settle_seconds == expected
    assert cfg.warnings == ()


def test_空は既定で警告しない(tmp_path: Path) -> None:
    cfg = load_config(_write_env(tmp_path, "ROOM_SETTLE_SECONDS=\n"))
    assert cfg.switch_settle_seconds == 5.0
    assert cfg.warnings == ()


@pytest.mark.parametrize("raw", ["-1", "abc", "inf", "nan", "1,5"])
def test_不正な上限は既定にして判断を残す(tmp_path: Path, raw: str) -> None:
    cfg = load_config(_write_env(tmp_path, f"ROOM_SETTLE_SECONDS={raw}\n"))
    assert cfg.switch_settle_seconds == 5.0
    assert any("ROOM_SETTLE_SECONDS" in w for w in cfg.warnings)


@pytest.mark.parametrize(
    "waited, limit, expected",
    [
        (0.0, 5.0, 1.5),
        (1.5, 5.0, 1.5),
        (4.5, 5.0, 0.5),  # 残りが、間隔より短いときは、その残りだけ
        (5.0, 5.0, 0.0),
        (0.0, 0.0, 0.0),  # 上限が 0 なら待たない
        (0.0, 1.0, 1.0),
        (6.0, 5.0, 0.0),
    ],
)
def test_待つ秒数の決め方(waited: float, limit: float, expected: float) -> None:
    assert settle_step(waited, limit) == pytest.approx(expected)


def test_間隔は1_5秒() -> None:
    assert SETTLE_INTERVAL_SECONDS == 1.5


# ---- 個別切替 ----


def test_指示のあと_待ってから取り直す(switchbot: FakeSwitchBot, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(device_service, "_sleep", lambda _seconds: switchbot.events.append("sleep"))

    result = switch_device("indirect_light", "off", actor="画面の利用者")

    assert switchbot.events == ["command", "sleep", "status"]  # 指示 → 待つ → 取得（指示の直後には取得しない）
    assert result.result == {"status": "ok", "state": "off"}


def test_反映が遅れても_目標の状態になるまで取り直す(
    switchbot: FakeSwitchBot, sleeps: list[float], log_dir: Path
) -> None:
    switchbot.lag_reads[ID_INDIRECT] = 2  # 最初の 2 回の取得は、古い値（ON）を返す

    result = switch_device("indirect_light", "off", actor="画面の利用者")

    assert result.result == {"status": "ok", "state": "off"}  # 失敗とは示されない
    assert sleeps == [1.5, 1.5, 1.5]
    assert switchbot.status_calls == [ID_INDIRECT] * 3
    assert "取得回数=3" in _log(log_dir)
    assert "目標と異なる" not in _log(log_dir)


def test_すぐ反映されれば_1回で終わる(switchbot: FakeSwitchBot, sleeps: list[float], log_dir: Path) -> None:
    switch_device("indoor_speaker", "on", actor="画面の利用者")
    assert sleeps == [1.5]
    assert switchbot.status_calls == [ID_INDOOR]
    assert "取得回数=1" in _log(log_dir)


def test_反映されないままなら_上限で打ち切り_最後の値を返す(
    switchbot: FakeSwitchBot, sleeps: list[float], log_dir: Path
) -> None:
    switchbot.apply_commands = False  # 指示は通るが、状態は変わらない

    result = switch_device("indirect_light", "off", actor="画面の利用者")

    assert result.result == {"status": "ok", "state": "on"}  # 取得した値のまま（目標と異なる）
    assert sleeps == [1.5, 1.5, 1.5, 0.5]
    assert sum(sleeps) == pytest.approx(5.0)  # 上限（5 秒）を超えて待たない
    assert len(switchbot.status_calls) == 4
    assert "目標と異なる" in _log(log_dir)


def test_上限を変えられる(
    switchbot: FakeSwitchBot, sleeps: list[float], monkeypatch: pytest.MonkeyPatch
) -> None:
    switchbot.apply_commands = False
    set_limit(monkeypatch, 3.0)
    switch_device("indirect_light", "off", actor="画面の利用者")
    assert sleeps == [1.5, 1.5]


def test_上限が0なら_待たずに1回だけ取得する(
    switchbot: FakeSwitchBot, sleeps: list[float], monkeypatch: pytest.MonkeyPatch
) -> None:
    switchbot.apply_commands = False
    set_limit(monkeypatch, 0.0)
    switch_device("indirect_light", "off", actor="画面の利用者")
    assert sleeps == []
    assert len(switchbot.status_calls) == 1


def test_取得の一時的な失敗は_取り直して回復する(switchbot: FakeSwitchBot, sleeps: list[float]) -> None:
    switchbot.status_failures[ID_INDIRECT] = 1  # 最初の取得だけ失敗する

    result = switch_device("indirect_light", "off", actor="画面の利用者")

    assert result.result == {"status": "ok", "state": "off"}
    assert sleeps == [1.5, 1.5]


def test_取得が失敗し続けたら_上限でerrorを返す(switchbot: FakeSwitchBot, sleeps: list[float]) -> None:
    switchbot.status_failures[ID_INDIRECT] = 99

    result = switch_device("indirect_light", "off", actor="画面の利用者")

    assert result.result == {"status": "error", "state": None}
    assert sum(sleeps) == pytest.approx(5.0)


def test_玄関ドアも反映を待つ(switchbot: FakeSwitchBot, sleeps: list[float]) -> None:
    switchbot.lag_reads[ID_DOOR] = 3  # 施錠・開錠は、反映に時間がかかる

    result = switch_device("front_door", "unlocked", actor="画面の利用者")

    assert result.result == {"status": "ok", "state": "unlocked", "battery": 35}
    assert sleeps == [1.5, 1.5, 1.5, 0.5]  # 4 回目は、上限（5 秒）までの残りだけ待つ。5.0 秒の時点で反映を確認できる


def test_指示が失敗したときは_待たない(switchbot: FakeSwitchBot, sleeps: list[float]) -> None:
    from app.errors import DeviceOperationError

    switchbot.command_errors[ID_INDIRECT] = failure()
    with pytest.raises(DeviceOperationError):
        switch_device("indirect_light", "off", actor="画面の利用者")
    assert sleeps == []
    assert switchbot.status_calls == []


def test_電灯は何も指示せず_待たない(switchbot: FakeSwitchBot, sleeps: list[float]) -> None:
    result = switch_device("ceiling_light", "on", actor="画面の利用者")
    assert result.applied is False
    assert sleeps == []
    assert switchbot.status_calls == []


def test_APIの応答は_反映を待った結果を返す(switchbot: FakeSwitchBot, sleeps: list[float]) -> None:
    ensure_feature()
    user_id = insert_user(unique("room_settle"))
    assign_feature(user_id)
    client = TestClient(room_app)
    client.cookies.set("session_id", str(insert_session(user_id, load_config().session_timeout_minutes)))
    switchbot.lag_reads[ID_INDIRECT] = 2

    res = client.put("/devices/indirect_light/state", json={"state": "off"})

    assert res.status_code == 200
    assert res.json()["result"] == {"status": "ok", "state": "off"}  # 画面に「失敗」と出ない
    assert sleeps == [1.5, 1.5, 1.5]


# ---- 一括切替 ----


def test_一括切替のあと_反映が遅れても_目標の状態になるまで取り直す(
    switchbot: FakeSwitchBot, sleeps: list[float]
) -> None:
    switchbot.statuses[ID_INDOOR] = {"power": "off"}
    switchbot.statuses[ID_BEDSIDE] = {"power": "on"}
    switchbot.lag_reads[ID_INDOOR] = 1
    switchbot.lag_reads[ID_BEDSIDE] = 2

    result = run_scene("indoor_speaker", actor="画面の利用者")  # 屋内 ON・枕元 OFF

    devices = result.snapshot.devices  # type: ignore[union-attr]
    assert devices["indoor_speaker"] == {"status": "ok", "state": "on"}
    assert devices["bedside_speaker"] == {"status": "ok", "state": "off"}
    assert sleeps == [1.5, 1.5, 1.5]  # 遅い方（枕元）が反映されるまで


def test_一括切替_反映されないままなら_上限で打ち切る(switchbot: FakeSwitchBot, sleeps: list[float]) -> None:
    switchbot.apply_commands = False
    result = run_scene("out", actor="画面の利用者")
    assert sum(sleeps) == pytest.approx(5.0)
    assert result.outcome == "success"  # 指示の成否は、指示が通ったかで決まる
    assert result.snapshot.devices["indirect_light"]["state"] == "on"  # type: ignore[union-attr]


def test_一括切替_全機器の指示が失敗したときは_待たない(switchbot: FakeSwitchBot, sleeps: list[float]) -> None:
    for device_id in (ID_INDIRECT, ID_INDOOR, ID_BEDSIDE):
        switchbot.command_errors[device_id] = failure()
    result = run_scene("out", actor="画面の利用者")
    assert result.outcome == "failure"
    assert sleeps == []  # 待つ対象（成功した機器）が無い


def test_一括切替_一部失敗でも_成功した機器の反映を待つ(switchbot: FakeSwitchBot, sleeps: list[float]) -> None:
    switchbot.statuses[ID_INDOOR] = {"power": "off"}
    switchbot.statuses[ID_BEDSIDE] = {"power": "on"}
    switchbot.command_errors[ID_BEDSIDE] = failure()  # 枕元の OFF は失敗
    switchbot.lag_reads[ID_INDOOR] = 1

    result = run_scene("indoor_speaker", actor="画面の利用者")

    assert result.outcome == "partial"
    devices = result.snapshot.devices  # type: ignore[union-attr]
    assert devices["indoor_speaker"]["state"] == "on"  # 成功した分の反映を待った
    assert devices["bedside_speaker"]["state"] == "on"  # 失敗した分は、元のまま
    assert sleeps == [1.5, 1.5]


def test_一括切替の電灯だけの結果は_待つ対象にならない(switchbot: FakeSwitchBot, sleeps: list[float]) -> None:
    switchbot.lag_reads[ID_INDIRECT] = 1
    run_scene("ceiling_light", actor="画面の利用者")  # 電灯 ON（未実装）と、間接照明 OFF
    assert sleeps == [1.5, 1.5]  # 間接照明（成功した機器）の反映だけを待つ


# ---- 定期実行 ----


def test_定期実行は取り直さないので_待たない(switchbot: FakeSwitchBot, sleeps: list[float]) -> None:
    from datetime import datetime, time

    from app import repos
    from app.timeutil import JST

    user_id = insert_user(unique("room_settle_job"))
    schedule_id = repos.insert_room_schedule(user_id, "daily", (), time(7, 0), "out", True)
    row = repos.get_room_schedule(schedule_id)
    assert row is not None
    try:
        reports = runner_service.run_once(now=datetime(2026, 10, 1, 7, 0, 30, tzinfo=JST), schedules=[row])
    finally:
        repos.delete_room_schedule(schedule_id)

    assert reports[0].outcome == "success"
    assert sleeps == []  # ジョブは、結果を画面に返さないので、反映を待たない
    assert switchbot.status_calls == []  # 取り直しもしない
