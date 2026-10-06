from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import load_config
from app.logger import LOG_FILE
from app.main import app as room_app
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
from helpers import assign_feature, ensure_feature, insert_api_key, insert_session, insert_user, unique

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+09:00$")


def _log_text(log_dir: Path) -> str:
    return (log_dir / LOG_FILE).read_text(encoding="utf-8")


def _client() -> TestClient:
    ensure_feature()
    user_id = insert_user(unique("room_switch"))
    assign_feature(user_id)
    client = TestClient(room_app)
    client.cookies.set(
        "session_id", str(insert_session(user_id, load_config().session_timeout_minutes))
    )
    return client


def _put(client: TestClient, device: str, body: object | None) -> object:
    return client.put(f"/devices/{device}/state", json=body)


# ---- 正常系 ----


@pytest.mark.parametrize(
    "device, device_id, target, command, expected",
    [
        ("indirect_light", ID_INDIRECT, "off", "turnOff", "off"),
        ("indirect_light", ID_INDIRECT, "on", "turnOn", "on"),
        ("indoor_speaker", ID_INDOOR, "on", "turnOn", "on"),
        ("bedside_speaker", ID_BEDSIDE, "off", "turnOff", "off"),
    ],
)
def test_照明とスピーカーはON_OFFの指示を送る(
    switchbot: FakeSwitchBot,
    device: str,
    device_id: str,
    target: str,
    command: str,
    expected: str,
) -> None:
    res = _put(_client(), device, {"state": target})

    assert res.status_code == 200  # type: ignore[attr-defined]
    body = res.json()  # type: ignore[attr-defined]
    assert body["device"] == device
    assert body["applied"] is True
    assert ISO.match(body["fetched_at"])
    assert body["result"] == {"status": "ok", "state": expected}
    # 指示は 1 回だけ、対象の機器にだけ送られる（他の機器は変えない）
    assert switchbot.commands == [(device_id, command)]


@pytest.mark.parametrize(
    "target, command, expected", [("unlocked", "unlock", "unlocked"), ("locked", "lock", "locked")]
)
def test_玄関ドアは施錠_開錠の指示を送る(
    switchbot: FakeSwitchBot, target: str, command: str, expected: str
) -> None:
    res = _put(_client(), "front_door", {"state": target})

    assert res.status_code == 200  # type: ignore[attr-defined]
    assert res.json()["result"] == {  # type: ignore[attr-defined]
        "status": "ok",
        "state": expected,
        "battery": 35,
    }
    assert switchbot.commands == [(ID_DOOR, command)]


# ---- 電灯（調光パターン） ----

# 4 種のパターンの値（requirements.md の用語表）
PATTERN_VALUES = {
    "full": (100, 6200),
    "reading": (80, 5000),
    "relax": (50, 3000),
    "night": (10, 2700),
}


def _turn_on_calls(pattern: str) -> list[tuple[str, str, str]]:
    brightness, color_temperature = PATTERN_VALUES[pattern]
    return [
        (ID_CEILING, "turnOn", "default"),
        (ID_CEILING, "setBrightness", str(brightness)),
        (ID_CEILING, "setColorTemperature", str(color_temperature)),
    ]


def test_電灯をONにすると_既定のパターンで3つの指示を順に1回ずつ送る(switchbot: FakeSwitchBot) -> None:
    res = _put(_client(), "ceiling_light", {"state": "on"})

    assert res.status_code == 200  # type: ignore[attr-defined]
    body = res.json()  # type: ignore[attr-defined]
    assert body["device"] == "ceiling_light"
    assert body["applied"] is True
    assert ISO.match(body["fetched_at"])
    assert body["result"] == {"status": "ok", "state": "on"}  # implemented・明るさ・色温度を含まない
    assert switchbot.calls == _turn_on_calls("full")


@pytest.mark.parametrize("pattern", list(PATTERN_VALUES))
def test_電灯をONにするとき_選んだパターンの明るさと色温度を送る(switchbot: FakeSwitchBot, pattern: str) -> None:
    res = _put(_client(), "ceiling_light", {"state": "on", "pattern": pattern})

    assert res.status_code == 200  # type: ignore[attr-defined]
    assert res.json()["result"] == {"status": "ok", "state": "on"}  # type: ignore[attr-defined]
    assert switchbot.calls == _turn_on_calls(pattern)


def test_点灯中の電灯に別のパターンを指定しても3つの指示を送る(switchbot: FakeSwitchBot) -> None:
    switchbot.statuses[ID_CEILING] = {"power": "on", "brightness": 100, "colorTemperature": 6200}

    res = _put(_client(), "ceiling_light", {"state": "on", "pattern": "night"})

    assert res.status_code == 200  # type: ignore[attr-defined]
    assert res.json()["result"] == {"status": "ok", "state": "on"}  # type: ignore[attr-defined]
    assert switchbot.calls == _turn_on_calls("night")


def test_電灯をOFFにするとturnOffだけを送る(switchbot: FakeSwitchBot) -> None:
    switchbot.statuses[ID_CEILING] = {"power": "on", "brightness": 80, "colorTemperature": 5000}

    res = _put(_client(), "ceiling_light", {"state": "off"})

    assert res.status_code == 200  # type: ignore[attr-defined]
    assert res.json()["result"] == {"status": "ok", "state": "off"}  # type: ignore[attr-defined]
    assert switchbot.calls == [(ID_CEILING, "turnOff", "default")]


def test_電灯の切替は他の機器へ指示しない(switchbot: FakeSwitchBot) -> None:
    _put(_client(), "ceiling_light", {"state": "on", "pattern": "reading"})
    assert {device_id for device_id, _, _ in switchbot.calls} == {ID_CEILING}


def test_電灯の切替のログに_パターン名が残る(switchbot: FakeSwitchBot, log_dir: Path) -> None:
    _put(_client(), "ceiling_light", {"state": "on", "pattern": "reading"})
    log = _log_text(log_dir)
    assert "機器切替要求 device=ceiling_light target=on" in log
    assert "パターン=reading" in log
    assert "機器切替成功 device=ceiling_light target=on パターン=reading" in log


def test_パターンを省略した電灯のONは_ログに既定のパターンが残る(switchbot: FakeSwitchBot, log_dir: Path) -> None:
    _put(_client(), "ceiling_light", {"state": "on"})
    assert "機器切替成功 device=ceiling_light target=on パターン=full" in _log_text(log_dir)


@pytest.mark.parametrize(
    "device, body",
    [
        ("ceiling_light", {"state": "on", "pattern": "dark"}),  # 4 種以外
        ("ceiling_light", {"state": "on", "pattern": ""}),
        ("ceiling_light", {"state": "on", "pattern": "FULL"}),
        ("ceiling_light", {"state": "off", "pattern": "full"}),  # OFF には指定できない
        ("indirect_light", {"state": "on", "pattern": "full"}),  # 電灯以外には指定できない
        ("indoor_speaker", {"state": "on", "pattern": "night"}),
        ("bedside_speaker", {"state": "off", "pattern": "night"}),
        ("front_door", {"state": "locked", "pattern": "full"}),
    ],
)
def test_不正な調光パターンの指定は400で何も指示しない(
    switchbot: FakeSwitchBot, device: str, body: object, log_dir: Path
) -> None:
    res = _put(_client(), device, body)

    assert res.status_code == 400  # type: ignore[attr-defined]
    assert res.json() == {"detail": "入力が不正です"}  # type: ignore[attr-defined]
    assert switchbot.commands == []
    assert "機器切替失敗" in _log_text(log_dir)


def test_途中の指示が失敗したら残りを送らず502_状態を調べて残す(
    switchbot: FakeSwitchBot, log_dir: Path
) -> None:
    switchbot.step_errors[(ID_CEILING, "setBrightness")] = failure()

    res = _put(_client(), "ceiling_light", {"state": "on", "pattern": "reading"})

    assert res.status_code == 502  # type: ignore[attr-defined]
    assert res.json() == {"detail": "機器を操作できませんでした"}  # type: ignore[attr-defined]
    # 点灯は送られ、明るさで失敗し、色温度は送られない
    assert [c for _, c, _ in switchbot.calls] == ["turnOn", "setBrightness"]
    log = _log_text(log_dir)
    assert "機器切替失敗 device=ceiling_light target=on パターン=reading" in log
    assert "失敗した指示=setBrightness（2/3）" in log
    assert "機器切替失敗の後の状態 device=ceiling_light 取得した状態=on" in log  # 点灯したまま


def test_最初の指示が失敗したら502で_状態の取り直しはしない(switchbot: FakeSwitchBot, log_dir: Path) -> None:
    switchbot.step_errors[(ID_CEILING, "turnOn")] = failure()

    res = _put(_client(), "ceiling_light", {"state": "on"})

    assert res.status_code == 502  # type: ignore[attr-defined]
    assert [c for _, c, _ in switchbot.calls] == ["turnOn"]
    assert switchbot.status_calls == []
    assert "機器切替失敗の後の状態" not in _log_text(log_dir)


def test_電灯のOFFの失敗は502(switchbot: FakeSwitchBot) -> None:
    switchbot.command_errors[ID_CEILING] = failure()
    res = _put(_client(), "ceiling_light", {"state": "off"})
    assert res.status_code == 502  # type: ignore[attr-defined]
    assert [c for _, c, _ in switchbot.calls] == ["turnOff"]


def test_電灯の識別子と認証情報が応答とログに出ない(switchbot: FakeSwitchBot, log_dir: Path) -> None:
    switchbot.step_errors[(ID_CEILING, "setColorTemperature")] = failure()
    ok = _put(_client(), "ceiling_light", {"state": "off"}).text  # type: ignore[attr-defined]
    ng = _put(_client(), "ceiling_light", {"state": "on"}).text  # type: ignore[attr-defined]
    log = _log_text(log_dir)
    for secret in (ID_CEILING, TEST_TOKEN, TEST_SECRET):
        assert secret not in ok and secret not in ng and secret not in log


# ---- 入力不正・対象なし ----


@pytest.mark.parametrize(
    "device, body",
    [
        ("front_door", {"state": "on"}),  # 玄関ドアに on
        ("indirect_light", {"state": "locked"}),  # 照明に locked
        ("ceiling_light", {"state": "locked"}),
        ("indoor_speaker", {"state": "toggle"}),  # 「反転」は受けない
        ("indoor_speaker", {"state": ""}),
        ("indoor_speaker", {}),  # state が無い
        ("indoor_speaker", {"state": None}),
        ("indoor_speaker", {"state": 1}),  # 型が違う
    ],
)
def test_機器に合わない_欠けたstateは400(
    switchbot: FakeSwitchBot, device: str, body: object
) -> None:
    res = _put(_client(), device, body)
    assert res.status_code == 400  # type: ignore[attr-defined]
    assert res.json() == {"detail": "入力が不正です"}  # type: ignore[attr-defined]
    assert switchbot.commands == []


def test_本文なしは400(switchbot: FakeSwitchBot) -> None:
    res = _client().put("/devices/indirect_light/state")
    assert res.status_code == 400
    assert switchbot.commands == []


def test_不明な機器は404(switchbot: FakeSwitchBot) -> None:
    for body in ({"state": "on"}, {"state": "nonsense"}, None):
        res = _put(_client(), "no_such_device", body)
        assert res.status_code == 404  # type: ignore[attr-defined]
        assert res.json() == {"detail": "対象がありません"}  # type: ignore[attr-defined]
    assert switchbot.commands == []


# ---- SwitchBot の失敗 ----


def test_指示の失敗は502で状態は変わらず再試行しない(switchbot: FakeSwitchBot, log_dir: Path) -> None:
    switchbot.command_errors[ID_INDIRECT] = failure()

    res = _put(_client(), "indirect_light", {"state": "off"})

    assert res.status_code == 502  # type: ignore[attr-defined]
    assert res.json() == {"detail": "機器を操作できませんでした"}  # type: ignore[attr-defined]
    assert switchbot.commands == [(ID_INDIRECT, "turnOff")]  # 1 回だけ
    assert switchbot.statuses[ID_INDIRECT] == {"power": "on"}  # 状態は元のまま
    assert "機器切替失敗 device=indirect_light target=off" in _log_text(log_dir)


def test_指示は成功しても取得した値が目標と違えば取得した値を返す(
    switchbot: FakeSwitchBot, log_dir: Path
) -> None:
    switchbot.apply_commands = False  # 指示は通るが状態が変わらない

    res = _put(_client(), "indirect_light", {"state": "off"})

    assert res.status_code == 200  # type: ignore[attr-defined]
    assert res.json()["result"] == {"status": "ok", "state": "on"}  # type: ignore[attr-defined]
    assert "目標と異なる" in _log_text(log_dir)


def test_指示は成功したが取得し直しに失敗したらerrorを返す(switchbot: FakeSwitchBot) -> None:
    switchbot.fail_status_after_command.add(ID_INDIRECT)

    res = _put(_client(), "indirect_light", {"state": "off"})

    assert res.status_code == 200  # type: ignore[attr-defined]
    body = res.json()  # type: ignore[attr-defined]
    assert body["applied"] is True
    assert body["result"] == {"status": "error", "state": None}


# ---- 認証・ログ ----


def test_未ログインは401(switchbot: FakeSwitchBot) -> None:
    res = TestClient(room_app).put("/devices/indirect_light/state", json={"state": "on"})
    assert res.status_code == 401
    assert switchbot.commands == []


def test_APIキーでも切り替えられ主体が記録される(switchbot: FakeSwitchBot, log_dir: Path) -> None:
    ensure_feature()
    user_id = insert_user(unique("room_switch_key"))
    assign_feature(user_id)
    key = "rk_" + unique("k") + "_secretsecretsecret"
    insert_api_key(user_id, key)

    res = TestClient(room_app).put(
        "/devices/front_door/state",
        json={"state": "unlocked"},
        headers={"Authorization": f"Bearer {key}"},
    )

    assert res.status_code == 200
    assert switchbot.commands == [(ID_DOOR, "unlock")]
    log = _log_text(log_dir)
    assert "主体=API の利用者" in log
    assert "機器切替成功 device=front_door target=unlocked" in log


def test_画面の利用者の操作が記録される(switchbot: FakeSwitchBot, log_dir: Path) -> None:
    _put(_client(), "bedside_speaker", {"state": "off"})
    log = _log_text(log_dir)
    assert "機器切替要求 device=bedside_speaker target=off 主体=画面の利用者" in log
    assert "機器切替成功 device=bedside_speaker target=off" in log


def test_認証情報と機器の識別子が応答とログに出ない(switchbot: FakeSwitchBot, log_dir: Path) -> None:
    switchbot.command_errors[ID_INDOOR] = failure()
    client = _client()
    texts = [
        _put(client, "indirect_light", {"state": "on"}).text,  # type: ignore[attr-defined]
        _put(client, "indoor_speaker", {"state": "on"}).text,  # type: ignore[attr-defined]
        _log_text(log_dir),
    ]
    for text in texts:
        for secret in (ID_INDIRECT, ID_INDOOR, ID_BEDSIDE, ID_DOOR, TEST_TOKEN, TEST_SECRET):
            assert secret not in text
