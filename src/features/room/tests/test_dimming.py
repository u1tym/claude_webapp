"""電灯の調光パターン（固定 4 種）の定義と、GET /dimming-patterns のテスト（T-030）。"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import dimming
from app.config import load_config
from app.logger import LOG_FILE
from app.main import app as room_app
from helpers import assign_feature, ensure_feature, insert_api_key, insert_session, insert_user, unique


def _log_text(log_dir: Path) -> str:
    return (log_dir / LOG_FILE).read_text(encoding="utf-8")


def _cookie_client() -> TestClient:
    ensure_feature()
    user_id = insert_user(unique("room_dimming"))
    assign_feature(user_id)
    client = TestClient(room_app)
    client.cookies.set("session_id", str(insert_session(user_id, load_config().session_timeout_minutes)))
    return client


# ---- 定義 ----


def test_4種のパターンが_画面の並びで定義されている() -> None:
    assert [(p.id, p.name, p.brightness, p.color_temperature) for p in dimming.PATTERNS] == [
        ("full", "全灯", 100, 6200),
        ("reading", "読書", 80, 5000),
        ("relax", "くつろぎ", 50, 3000),
        ("night", "夜", 10, 2700),
    ]


def test_既定のパターンは全灯() -> None:
    assert dimming.DEFAULT_PATTERN_ID == "full"
    default = dimming.resolve(None)
    assert default is not None and default.id == "full"


def test_値は_SwitchBotの範囲に収まる() -> None:
    for pattern in dimming.PATTERNS:
        assert 1 <= pattern.brightness <= 100
        assert 2700 <= pattern.color_temperature <= 6500


def test_識別子で引ける_4種以外は引けない() -> None:
    assert dimming.find("reading") is not None
    for bad in ("dark", "", "FULL", "全灯"):
        assert dimming.find(bad) is None
        assert dimming.resolve(bad) is None


def test_点灯の指示は_点灯_明るさ_色温度の順() -> None:
    reading = dimming.find("reading")
    assert reading is not None
    assert dimming.turn_on_commands(reading) == (
        ("turnOn", "default"),
        ("setBrightness", "80"),
        ("setColorTemperature", "5000"),
    )


# ---- GET /dimming-patterns ----


def test_調光パターンは未ログインなら401() -> None:
    assert TestClient(room_app).get("/dimming-patterns").status_code == 401


def test_調光パターンは割当がなければ403() -> None:
    ensure_feature()
    user_id = insert_user(unique("room_dimming_noas"))
    client = TestClient(room_app)
    client.cookies.set("session_id", str(insert_session(user_id, load_config().session_timeout_minutes)))
    assert client.get("/dimming-patterns").status_code == 403


def test_調光パターンは4種と既定を返す(switchbot, log_dir: Path) -> None:  # type: ignore[no-untyped-def]
    res = _cookie_client().get("/dimming-patterns")

    assert res.status_code == 200
    assert res.json() == {
        "default": "full",
        "patterns": [
            {"id": "full", "name": "全灯", "brightness": 100, "color_temperature": 6200},
            {"id": "reading", "name": "読書", "brightness": 80, "color_temperature": 5000},
            {"id": "relax", "name": "くつろぎ", "brightness": 50, "color_temperature": 3000},
            {"id": "night", "name": "夜", "brightness": 10, "color_temperature": 2700},
        ],
    }
    assert "調光パターン取得要求" in _log_text(log_dir)


def test_調光パターンの取得は_SwitchBotへ問い合わせない(switchbot) -> None:  # type: ignore[no-untyped-def]
    _cookie_client().get("/dimming-patterns")
    assert switchbot.status_calls == [] and switchbot.commands == []


def test_調光パターンはAPIキーでも同じ内容を返す(switchbot, log_dir: Path) -> None:  # type: ignore[no-untyped-def]
    ensure_feature()
    user_id = insert_user(unique("room_dimming_key"))
    assign_feature(user_id)
    key = "rk_" + unique("k") + "_secretsecretsecret"
    insert_api_key(user_id, key)

    res = TestClient(room_app).get("/dimming-patterns", headers={"Authorization": f"Bearer {key}"})

    assert res.status_code == 200
    assert res.json() == _cookie_client().get("/dimming-patterns").json()
    assert "経路=api_key" in _log_text(log_dir)
