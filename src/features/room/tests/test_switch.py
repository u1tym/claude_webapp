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


@pytest.mark.parametrize("target", ["on", "off"])
def test_電灯は機器へ何も指示せずOFFを返す(switchbot: FakeSwitchBot, target: str) -> None:
    res = _put(_client(), "ceiling_light", {"state": target})

    assert res.status_code == 200  # type: ignore[attr-defined]
    body = res.json()  # type: ignore[attr-defined]
    assert body["applied"] is False
    assert body["result"] == {"status": "ok", "state": "off", "implemented": False}
    assert switchbot.commands == []
    assert switchbot.status_calls == []


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
