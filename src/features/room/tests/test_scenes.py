from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import load_config
from app.logger import LOG_FILE
from app.main import app as room_app
from app.services import device_service
from app.services.scene_service import SCENES, DeviceOutcome, overall_outcome
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
    user_id = insert_user(unique("room_scene"))
    assign_feature(user_id)
    client = TestClient(room_app)
    client.cookies.set(
        "session_id", str(insert_session(user_id, load_config().session_timeout_minutes))
    )
    return client


def _post(scene: str) -> object:
    return _client().post(f"/scenes/{scene}")


# 一括切替ごとに「機器へ送られる指示」。電灯を ON にするときは、調光の 3 つの指示（点灯・明るさ・色温度）を送る
EXPECTED_COMMANDS: dict[str, set[tuple[str, str]]] = {
    "indoor_speaker": {(ID_INDOOR, "turnOn"), (ID_BEDSIDE, "turnOff")},
    "bedside_speaker": {(ID_INDOOR, "turnOff"), (ID_BEDSIDE, "turnOn")},
    "ceiling_light": {
        (ID_CEILING, "turnOn"),
        (ID_CEILING, "setBrightness"),
        (ID_CEILING, "setColorTemperature"),
        (ID_INDIRECT, "turnOff"),
    },
    "indirect_light": {(ID_CEILING, "turnOff"), (ID_INDIRECT, "turnOn")},
    "out": {
        (ID_CEILING, "turnOff"),
        (ID_INDIRECT, "turnOff"),
        (ID_INDOOR, "turnOff"),
        (ID_BEDSIDE, "turnOff"),
    },
}


def test_一括切替の定義は要件どおり() -> None:
    assert SCENES == {
        "indoor_speaker": (("indoor_speaker", "on"), ("bedside_speaker", "off")),
        "bedside_speaker": (("indoor_speaker", "off"), ("bedside_speaker", "on")),
        "ceiling_light": (("ceiling_light", "on"), ("indirect_light", "off")),
        "indirect_light": (("ceiling_light", "off"), ("indirect_light", "on")),
        "out": (
            ("ceiling_light", "off"),
            ("indirect_light", "off"),
            ("indoor_speaker", "off"),
            ("bedside_speaker", "off"),
        ),
    }
    # 玄関ドアは、どの一括切替にも含まれない
    assert all(device != "front_door" for targets in SCENES.values() for device, _ in targets)


@pytest.mark.parametrize("scene", list(EXPECTED_COMMANDS))
def test_一括切替が要件どおりの指示を送る(switchbot: FakeSwitchBot, scene: str) -> None:
    res = _post(scene)

    assert res.status_code == 200  # type: ignore[attr-defined]
    body = res.json()  # type: ignore[attr-defined]
    assert body["scene"] == scene
    assert body["outcome"] == "success"
    assert ISO.match(body["fetched_at"])
    assert set(switchbot.commands) == EXPECTED_COMMANDS[scene]
    # 指示は機器ごとに 1 回だけ
    assert len(switchbot.commands) == len(EXPECTED_COMMANDS[scene])
    # 玄関ドアには指示が行かない
    assert all(device_id != ID_DOOR for device_id, _ in switchbot.commands)


def test_結果は定義の順で電灯も成功になる(switchbot: FakeSwitchBot) -> None:
    body = _post("ceiling_light").json()  # type: ignore[attr-defined]
    assert body["results"] == [
        {"device": "ceiling_light", "target": "on", "outcome": "success"},
        {"device": "indirect_light", "target": "off", "outcome": "success"},
    ]
    assert body["outcome"] == "success"
    assert "skipped" not in str(body)


def test_お出かけは4機器を消灯しスピーカーも切る(switchbot: FakeSwitchBot) -> None:
    body = _post("out").json()  # type: ignore[attr-defined]
    assert [r["device"] for r in body["results"]] == [
        "ceiling_light",
        "indirect_light",
        "indoor_speaker",
        "bedside_speaker",
    ]
    assert all(r["target"] == "off" for r in body["results"])
    devices = body["devices"]
    assert devices["indirect_light"]["state"] == "off"
    assert devices["indoor_speaker"]["state"] == "off"
    assert devices["bedside_speaker"]["state"] == "off"
    # 玄関ドアは変えない（施錠も開錠もしない）
    assert devices["front_door"] == {"status": "ok", "state": "locked", "battery": 35}


def test_実行後に全機器の状態を取得し直して返す(switchbot: FakeSwitchBot) -> None:
    body = _post("indoor_speaker").json()  # type: ignore[attr-defined]
    assert sorted(switchbot.status_calls) == sorted([ID_CEILING, ID_INDIRECT, ID_INDOOR, ID_BEDSIDE, ID_DOOR])
    assert body["devices"]["indoor_speaker"] == {"status": "ok", "state": "on"}
    assert body["devices"]["bedside_speaker"] == {"status": "ok", "state": "off"}
    assert body["devices"]["ceiling_light"] == {"status": "ok", "state": "off"}
    assert list(body["devices"]) == list(device_service.DEVICE_KEYS)


# ---- 一部失敗・全失敗 ----


def test_一部の機器が失敗したらpartialで成功した機器は元に戻さない(
    switchbot: FakeSwitchBot, log_dir: Path
) -> None:
    switchbot.statuses[ID_BEDSIDE] = {"power": "on"}
    switchbot.command_errors[ID_BEDSIDE] = failure()

    res = _post("indoor_speaker")

    assert res.status_code == 200  # type: ignore[attr-defined]
    body = res.json()  # type: ignore[attr-defined]
    assert body["outcome"] == "partial"
    assert body["results"] == [
        {"device": "indoor_speaker", "target": "on", "outcome": "success"},
        {"device": "bedside_speaker", "target": "off", "outcome": "failure"},
    ]
    # 成功した屋内スピーカーは ON のまま。元に戻す指示は送られない
    assert body["devices"]["indoor_speaker"]["state"] == "on"
    assert body["devices"]["bedside_speaker"]["state"] == "on"
    assert set(switchbot.commands) == {(ID_INDOOR, "turnOn"), (ID_BEDSIDE, "turnOff")}
    assert "全体=partial" in _log_text(log_dir)


def test_すべて失敗したらfailureでも200(switchbot: FakeSwitchBot) -> None:
    switchbot.command_errors[ID_INDOOR] = failure()
    switchbot.command_errors[ID_BEDSIDE] = failure()

    res = _post("bedside_speaker")

    assert res.status_code == 200  # type: ignore[attr-defined]
    body = res.json()  # type: ignore[attr-defined]
    assert body["outcome"] == "failure"
    assert [r["outcome"] for r in body["results"]] == ["failure", "failure"]


def test_電灯が含まれても失敗した機器があればpartialになる(switchbot: FakeSwitchBot) -> None:
    switchbot.command_errors[ID_INDIRECT] = failure()
    body = _post("out").json()  # type: ignore[attr-defined]
    assert body["outcome"] == "partial"
    outcomes = {r["device"]: r["outcome"] for r in body["results"]}
    assert outcomes == {
        "ceiling_light": "success",
        "indirect_light": "failure",
        "indoor_speaker": "success",
        "bedside_speaker": "success",
    }


def test_SwitchBotの設定が未完了なら全機器failureで200(
    switchbot: FakeSwitchBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(device_service, "build_client", lambda _cfg=None: None)

    res = _post("out")

    assert res.status_code == 200  # type: ignore[attr-defined]
    body = res.json()  # type: ignore[attr-defined]
    assert body["outcome"] == "failure"
    assert switchbot.commands == []
    assert body["devices"]["indirect_light"]["status"] == "error"


@pytest.mark.parametrize(
    "outcomes, expected",
    [
        (("success", "success"), "success"),
        (("failure", "failure"), "failure"),
        (("success", "failure"), "partial"),
        (("success", "success", "failure"), "partial"),
        (("failure", "failure", "success"), "partial"),
    ],
)
def test_全体の結果の判定(outcomes: tuple[str, ...], expected: str) -> None:
    results = tuple(DeviceOutcome("d", "off", o) for o in outcomes)
    assert overall_outcome(results) == expected


# ---- 対象なし・認証・ログ ----


def test_不明な一括切替は404で何も指示しない(switchbot: FakeSwitchBot) -> None:
    res = _post("no_such_scene")
    assert res.status_code == 404  # type: ignore[attr-defined]
    assert res.json() == {"detail": "対象がありません"}  # type: ignore[attr-defined]
    assert switchbot.commands == []


def test_未ログインは401で何も指示しない(switchbot: FakeSwitchBot) -> None:
    res = TestClient(room_app).post("/scenes/out")
    assert res.status_code == 401
    assert switchbot.commands == []


def test_APIキーでも実行でき主体が記録される(switchbot: FakeSwitchBot, log_dir: Path) -> None:
    ensure_feature()
    user_id = insert_user(unique("room_scene_key"))
    assign_feature(user_id)
    key = "rk_" + unique("k") + "_secretsecretsecret"
    insert_api_key(user_id, key)

    res = TestClient(room_app).post("/scenes/out", headers={"Authorization": f"Bearer {key}"})

    assert res.status_code == 200
    log = _log_text(log_dir)
    assert "一括切替要求 scene=out 主体=API の利用者" in log
    assert "一括切替結果 scene=out 主体=API の利用者 全体=success" in log


def test_画面の利用者の実行が機器ごとに記録される(switchbot: FakeSwitchBot, log_dir: Path) -> None:
    _post("ceiling_light")
    log = _log_text(log_dir)
    assert "一括切替要求 scene=ceiling_light 主体=画面の利用者" in log
    assert "device=ceiling_light target=on パターン=full 主体=画面の利用者 結果=success" in log
    assert "機器切替成功" not in log  # 一括切替では機器ごとの再取得をしない
    assert "一括切替結果 scene=ceiling_light" in log


def test_認証情報と機器の識別子が応答とログに出ない(switchbot: FakeSwitchBot, log_dir: Path) -> None:
    switchbot.command_errors[ID_INDOOR] = failure()
    client = _client()
    texts = [client.post("/scenes/indoor_speaker").text, client.post("/scenes/out").text]
    texts.append(_log_text(log_dir))
    for text in texts:
        for secret in (ID_CEILING, ID_INDIRECT, ID_INDOOR, ID_BEDSIDE, ID_DOOR, TEST_TOKEN, TEST_SECRET):
            assert secret not in text


# ---- 電灯選択と調光パターン ----

PATTERN_VALUES = {"full": (100, 6200), "reading": (80, 5000), "relax": (50, 3000), "night": (10, 2700)}


def _post_with(scene: str, body: object) -> object:
    return _client().post(f"/scenes/{scene}", json=body)


def _ceiling_calls(switchbot: FakeSwitchBot) -> list[tuple[str, str]]:
    return [(c, p) for d, c, p in switchbot.calls if d == ID_CEILING]


def test_電灯選択は本文なしなら既定のパターンで電灯をONにし_間接照明をOFFにする(switchbot: FakeSwitchBot) -> None:
    switchbot.statuses[ID_INDIRECT] = {"power": "on"}
    body = _post("ceiling_light").json()  # type: ignore[attr-defined]

    assert _ceiling_calls(switchbot) == [("turnOn", "default"), ("setBrightness", "100"), ("setColorTemperature", "6200")]
    assert body["devices"]["ceiling_light"] == {"status": "ok", "state": "on"}
    assert body["devices"]["indirect_light"] == {"status": "ok", "state": "off"}


@pytest.mark.parametrize("pattern", list(PATTERN_VALUES))
def test_電灯選択は選んだパターンで電灯をONにする(switchbot: FakeSwitchBot, pattern: str) -> None:
    res = _post_with("ceiling_light", {"pattern": pattern})

    assert res.status_code == 200  # type: ignore[attr-defined]
    brightness, color_temperature = PATTERN_VALUES[pattern]
    assert _ceiling_calls(switchbot) == [
        ("turnOn", "default"),
        ("setBrightness", str(brightness)),
        ("setColorTemperature", str(color_temperature)),
    ]
    assert res.json()["outcome"] == "success"  # type: ignore[attr-defined]


def test_パターンを省略した本文でも既定のパターンになる(switchbot: FakeSwitchBot) -> None:
    _post_with("ceiling_light", {})
    assert _ceiling_calls(switchbot)[1] == ("setBrightness", "100")


def test_間接照明選択とお出かけは電灯を実際にOFFにする(switchbot: FakeSwitchBot) -> None:
    switchbot.statuses[ID_CEILING] = {"power": "on", "brightness": 80, "colorTemperature": 5000}
    body = _post("indirect_light").json()  # type: ignore[attr-defined]
    assert _ceiling_calls(switchbot) == [("turnOff", "default")]
    assert body["devices"]["ceiling_light"] == {"status": "ok", "state": "off"}

    switchbot.statuses[ID_CEILING] = {"power": "on", "brightness": 80, "colorTemperature": 5000}
    switchbot.calls.clear()
    body = _post("out").json()  # type: ignore[attr-defined]
    assert _ceiling_calls(switchbot) == [("turnOff", "default")]
    assert body["devices"]["ceiling_light"] == {"status": "ok", "state": "off"}


@pytest.mark.parametrize("scene", ["indoor_speaker", "bedside_speaker", "indirect_light", "out"])
def test_電灯選択以外の一括切替で_パターンを指定すると400で何も指示しない(
    switchbot: FakeSwitchBot, scene: str, log_dir: Path
) -> None:
    res = _post_with(scene, {"pattern": "full"})

    assert res.status_code == 400  # type: ignore[attr-defined]
    assert res.json() == {"detail": "入力が不正です"}  # type: ignore[attr-defined]
    assert switchbot.commands == []
    assert "調光パターンは電灯選択だけで指定できる" in _log_text(log_dir)


@pytest.mark.parametrize("pattern", ["dark", "", "FULL"])
def test_4種以外のパターンは400で何も指示しない(switchbot: FakeSwitchBot, pattern: str) -> None:
    res = _post_with("ceiling_light", {"pattern": pattern})
    assert res.status_code == 400  # type: ignore[attr-defined]
    assert switchbot.commands == []


def test_不明な一括切替は_パターンつきでも404(switchbot: FakeSwitchBot) -> None:
    assert _post_with("no_such_scene", {"pattern": "full"}).status_code == 404  # type: ignore[attr-defined]


def test_電灯の調光の途中で失敗したら電灯はfailure_間接照明は成功でpartial(switchbot: FakeSwitchBot) -> None:
    switchbot.step_errors[(ID_CEILING, "setColorTemperature")] = failure()

    res = _post_with("ceiling_light", {"pattern": "night"})

    assert res.status_code == 200  # type: ignore[attr-defined]
    body = res.json()  # type: ignore[attr-defined]
    assert body["outcome"] == "partial"
    assert {r["device"]: r["outcome"] for r in body["results"]} == {
        "ceiling_light": "failure",
        "indirect_light": "success",
    }
    # 間接照明は元に戻さない。電灯は、点灯と明るさまで送られ、色温度で失敗した
    assert (ID_INDIRECT, "turnOff") in switchbot.commands
    assert [c for c, _ in _ceiling_calls(switchbot)] == ["turnOn", "setBrightness", "setColorTemperature"]


def test_電灯の点灯が失敗したら_残りの調光は送らない(switchbot: FakeSwitchBot) -> None:
    switchbot.step_errors[(ID_CEILING, "turnOn")] = failure()
    body = _post("ceiling_light").json()  # type: ignore[attr-defined]
    assert {r["device"]: r["outcome"] for r in body["results"]}["ceiling_light"] == "failure"
    assert [c for c, _ in _ceiling_calls(switchbot)] == ["turnOn"]


def test_電灯の反映が遅れても_目標の状態になるまで取り直す(switchbot: FakeSwitchBot, sleeps: list[float]) -> None:
    switchbot.lag_reads[ID_CEILING] = 2
    switchbot.statuses[ID_INDIRECT] = {"power": "on"}

    body = _post("ceiling_light").json()  # type: ignore[attr-defined]

    assert body["devices"]["ceiling_light"] == {"status": "ok", "state": "on"}
    assert sleeps == [1.5, 1.5, 1.5]


def test_電灯選択のログに_パターンの要求と結果が残る(switchbot: FakeSwitchBot, log_dir: Path) -> None:
    _post_with("ceiling_light", {"pattern": "reading"})
    log = _log_text(log_dir)
    assert "一括切替要求 scene=ceiling_light 主体=画面の利用者" in log and "パターン=reading" in log
    assert "device=ceiling_light target=on パターン=reading 主体=画面の利用者 結果=success" in log
    assert "全体=success ceiling_light=success indirect_light=success" in log
