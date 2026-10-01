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


# 一括切替ごとに「機器へ送られる指示」（電灯は未実装のため指示しない）
EXPECTED_COMMANDS: dict[str, set[tuple[str, str]]] = {
    "indoor_speaker": {(ID_INDOOR, "turnOn"), (ID_BEDSIDE, "turnOff")},
    "bedside_speaker": {(ID_INDOOR, "turnOff"), (ID_BEDSIDE, "turnOn")},
    "ceiling_light": {(ID_INDIRECT, "turnOff")},
    "indirect_light": {(ID_INDIRECT, "turnOn")},
    "out": {(ID_INDIRECT, "turnOff"), (ID_INDOOR, "turnOff"), (ID_BEDSIDE, "turnOff")},
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


def test_結果は定義の順で電灯はskipped(switchbot: FakeSwitchBot) -> None:
    body = _post("ceiling_light").json()  # type: ignore[attr-defined]
    assert body["results"] == [
        {"device": "ceiling_light", "target": "on", "outcome": "skipped"},
        {"device": "indirect_light", "target": "off", "outcome": "success"},
    ]
    assert body["outcome"] == "success"  # skipped は全体の判定に含めない


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
    assert sorted(switchbot.status_calls) == sorted([ID_INDIRECT, ID_INDOOR, ID_BEDSIDE, ID_DOOR])
    assert body["devices"]["indoor_speaker"] == {"status": "ok", "state": "on"}
    assert body["devices"]["bedside_speaker"] == {"status": "ok", "state": "off"}
    assert body["devices"]["ceiling_light"] == {"status": "ok", "state": "off", "implemented": False}
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
        "ceiling_light": "skipped",
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
        (("skipped", "success"), "success"),
        (("skipped", "failure"), "failure"),
        (("skipped", "success", "failure"), "partial"),
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
    assert "device=ceiling_light target=on 判断=未実装のため何も指示しない" in log
    assert "機器切替成功" not in log  # 一括切替では機器ごとの再取得をしない
    assert "一括切替結果 scene=ceiling_light" in log


def test_認証情報と機器の識別子が応答とログに出ない(switchbot: FakeSwitchBot, log_dir: Path) -> None:
    switchbot.command_errors[ID_INDOOR] = failure()
    client = _client()
    texts = [client.post("/scenes/indoor_speaker").text, client.post("/scenes/out").text]
    texts.append(_log_text(log_dir))
    for text in texts:
        for secret in (ID_INDIRECT, ID_INDOOR, ID_BEDSIDE, ID_DOOR, TEST_TOKEN, TEST_SECRET):
            assert secret not in text
