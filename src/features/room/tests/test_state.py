from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.logger import LOG_FILE
from app.main import app as room_app
from app.services import device_service
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
from app.config import load_config

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+09:00$")


def _log_text(log_dir: Path) -> str:
    return (log_dir / LOG_FILE).read_text(encoding="utf-8")


# ---- サービス層 ----


def test_5機器の状態と取得日時が返る(switchbot: FakeSwitchBot) -> None:
    snapshot = device_service.fetch_states().to_dict()

    assert ISO.match(snapshot["fetched_at"])
    assert snapshot["devices"] == {
        "ceiling_light": {"status": "ok", "state": "off"},
        "indirect_light": {"status": "ok", "state": "on"},
        "indoor_speaker": {"status": "ok", "state": "off"},
        "bedside_speaker": {"status": "ok", "state": "off"},
        "front_door": {"status": "ok", "state": "locked", "battery": 35},
    }
    assert list(snapshot["devices"]) == list(device_service.DEVICE_KEYS)


def test_5機器すべてをSwitchBotへ問い合わせる(switchbot: FakeSwitchBot) -> None:
    device_service.fetch_states()
    assert sorted(switchbot.status_calls) == sorted([ID_CEILING, ID_INDIRECT, ID_INDOOR, ID_BEDSIDE, ID_DOOR])


def test_電灯は電源だけを返し_明るさと色温度を含まない(switchbot: FakeSwitchBot) -> None:
    switchbot.statuses[ID_CEILING] = {"power": "on", "brightness": 40, "colorTemperature": 3000}
    assert device_service.fetch_states().devices["ceiling_light"] == {"status": "ok", "state": "on"}


def test_電灯の取得に失敗しても他に影響しない(switchbot: FakeSwitchBot, log_dir: Path) -> None:
    switchbot.statuses[ID_CEILING] = failure()
    devices = device_service.fetch_states().devices
    assert devices["ceiling_light"] == {"status": "error", "state": None}
    assert all(devices[key]["status"] == "ok" for key in ("indirect_light", "indoor_speaker", "bedside_speaker", "front_door"))
    assert "状態取得失敗 device=ceiling_light" in _log_text(log_dir)


@pytest.mark.parametrize("power", ["standby", None, 1])
def test_電灯の電源の値が想定外ならエラー(switchbot: FakeSwitchBot, power: object) -> None:
    switchbot.statuses[ID_CEILING] = {"power": power}
    assert device_service.fetch_states().devices["ceiling_light"] == {"status": "error", "state": None}


def test_1機器の失敗は他に影響しない(switchbot: FakeSwitchBot, log_dir: Path) -> None:
    switchbot.statuses[ID_INDOOR] = failure()

    devices = device_service.fetch_states().devices

    assert devices["indoor_speaker"] == {"status": "error", "state": None}
    assert devices["indirect_light"] == {"status": "ok", "state": "on"}
    assert devices["bedside_speaker"]["status"] == "ok"
    assert devices["front_door"]["status"] == "ok"
    assert "状態取得失敗 device=indoor_speaker" in _log_text(log_dir)


def test_全機器が失敗してもスナップショットを返す(switchbot: FakeSwitchBot) -> None:
    for key in (ID_CEILING, ID_INDIRECT, ID_INDOOR, ID_BEDSIDE, ID_DOOR):
        switchbot.statuses[key] = failure()

    devices = device_service.fetch_states().devices

    for key in ("ceiling_light", "indirect_light", "indoor_speaker", "bedside_speaker"):
        assert devices[key] == {"status": "error", "state": None}
    assert devices["front_door"] == {"status": "error", "state": None, "battery": None}


@pytest.mark.parametrize("lock_state", ["jammed", "unknown", None, ""])
def test_施錠中_開錠中以外の玄関ドアは取得エラー(switchbot: FakeSwitchBot, lock_state: object) -> None:
    switchbot.statuses[ID_DOOR] = {"lockState": lock_state, "battery": 80}
    assert device_service.fetch_states().devices["front_door"] == {
        "status": "error",
        "state": None,
        "battery": None,
    }


def test_開錠中の玄関ドア(switchbot: FakeSwitchBot) -> None:
    switchbot.statuses[ID_DOOR] = {"lockState": "unlocked", "battery": 0}
    assert device_service.fetch_states().devices["front_door"] == {
        "status": "ok",
        "state": "unlocked",
        "battery": 0,
    }


@pytest.mark.parametrize("battery", [None, "35", -1, 101, True, 3.5])
def test_電池残量が取れない値ならNone(switchbot: FakeSwitchBot, battery: object) -> None:
    switchbot.statuses[ID_DOOR] = {"lockState": "locked", "battery": battery}
    door = device_service.fetch_states().devices["front_door"]
    assert door["status"] == "ok"
    assert door["battery"] is None


@pytest.mark.parametrize("power", ["standby", None, 1])
def test_電源の値が想定外ならエラー(switchbot: FakeSwitchBot, power: object) -> None:
    switchbot.statuses[ID_INDIRECT] = {"power": power}
    assert device_service.fetch_states().devices["indirect_light"] == {
        "status": "error",
        "state": None,
    }


def test_認証情報が未設定なら全機器がエラー(
    monkeypatch: pytest.MonkeyPatch, log_dir: Path
) -> None:
    import dataclasses

    cfg = dataclasses.replace(load_config(), switchbot_token="", switchbot_secret="")
    monkeypatch.setattr(device_service, "load_config", lambda: cfg)

    devices = device_service.fetch_states().devices

    assert all(devices[key]["status"] == "error" for key in device_service.DEVICE_KEYS)
    assert "認証情報が未設定" in _log_text(log_dir)


def test_機器の識別子が未設定ならその機器だけエラー(
    switchbot: FakeSwitchBot, monkeypatch: pytest.MonkeyPatch, log_dir: Path
) -> None:
    import dataclasses

    cfg = dataclasses.replace(
        load_config(),
        switchbot_token=TEST_TOKEN,
        switchbot_secret=TEST_SECRET,
        device_ceiling_light_id=ID_CEILING,
        device_indirect_light_id=ID_INDIRECT,
        device_indoor_speaker_id="",
        device_bedside_speaker_id=ID_BEDSIDE,
        device_front_door_id=ID_DOOR,
    )
    monkeypatch.setattr(device_service, "load_config", lambda: cfg)

    devices = device_service.fetch_states().devices

    assert devices["indoor_speaker"]["status"] == "error"
    assert devices["indirect_light"]["status"] == "ok"
    assert "機器の識別子が未設定" in _log_text(log_dir)


def test_電灯の識別子が未設定なら電灯だけエラー(
    switchbot: FakeSwitchBot, monkeypatch: pytest.MonkeyPatch, log_dir: Path
) -> None:
    import dataclasses

    cfg = dataclasses.replace(device_service.load_config(), device_ceiling_light_id="")
    monkeypatch.setattr(device_service, "load_config", lambda: cfg)

    devices = device_service.fetch_states().devices

    assert devices["ceiling_light"] == {"status": "error", "state": None}
    assert devices["indirect_light"]["status"] == "ok"
    assert "状態取得失敗 device=ceiling_light 理由=機器の識別子が未設定" in _log_text(log_dir)


def test_認証情報と機器の識別子が応答とログに出ない(
    switchbot: FakeSwitchBot, log_dir: Path
) -> None:
    switchbot.statuses[ID_INDOOR] = failure()
    body = str(device_service.fetch_states().to_dict())
    log = _log_text(log_dir)
    for secret in (ID_CEILING, ID_INDIRECT, ID_INDOOR, ID_BEDSIDE, ID_DOOR, TEST_TOKEN, TEST_SECRET):
        assert secret not in body
        assert secret not in log


# ---- GET /state ----


def _cookie_client() -> TestClient:
    ensure_feature()
    user_id = insert_user(unique("room_state"))
    assign_feature(user_id)
    client = TestClient(room_app)
    client.cookies.set(
        "session_id", str(insert_session(user_id, load_config().session_timeout_minutes))
    )
    return client


def test_stateは未ログインなら401() -> None:
    assert TestClient(room_app).get("/state").status_code == 401


def test_stateはCookieで200と状態を返す(switchbot: FakeSwitchBot, log_dir: Path) -> None:
    res = _cookie_client().get("/state")
    assert res.status_code == 200
    body = res.json()
    assert ISO.match(body["fetched_at"])
    assert body["devices"]["front_door"] == {"status": "ok", "state": "locked", "battery": 35}
    assert "状態取得要求" in _log_text(log_dir)
    assert "経路=session" in _log_text(log_dir)


def test_stateは機器が失敗しても200(switchbot: FakeSwitchBot) -> None:
    for key in (ID_INDIRECT, ID_INDOOR, ID_BEDSIDE, ID_DOOR):
        switchbot.statuses[key] = failure()
    res = _cookie_client().get("/state")
    assert res.status_code == 200
    assert res.json()["devices"]["indirect_light"] == {"status": "error", "state": None}


def test_stateはAPIキーでも同じ内容を返す(switchbot: FakeSwitchBot, log_dir: Path) -> None:
    ensure_feature()
    user_id = insert_user(unique("room_state_key"))
    assign_feature(user_id)
    key = "rk_" + unique("k") + "_secretsecretsecret"
    insert_api_key(user_id, key)

    res = TestClient(room_app).get("/state", headers={"Authorization": f"Bearer {key}"})

    assert res.status_code == 200
    assert res.json() == _cookie_client().get("/state").json() | {
        "fetched_at": res.json()["fetched_at"]
    }
    assert "経路=api_key" in _log_text(log_dir)


def test_stateの応答に秘密情報が含まれない(switchbot: FakeSwitchBot) -> None:
    text = _cookie_client().get("/state").text
    for secret in (ID_CEILING, ID_INDIRECT, ID_INDOOR, ID_BEDSIDE, ID_DOOR, TEST_TOKEN, TEST_SECRET):
        assert secret not in text
