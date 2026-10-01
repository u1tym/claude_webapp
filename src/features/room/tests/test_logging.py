"""操作ログの点検（REQ-012、REQ-013）。

全種類の操作を実行して、ログの形式と内容、秘密情報が出ないことを確認する。
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import repos
from app.config import load_config
from app.db import get_conn
from app.logger import LOG_FILE, set_source
from app.main import app as room_app
from app.security import hash_api_key
from app.services.runner_service import run_once
from app.timeutil import JST
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

LINE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} (INF|WRN|ERR|DBG) \[(api|job)\] \S.*$")


def _lines(log_dir: Path) -> list[str]:
    return (log_dir / LOG_FILE).read_text(encoding="utf-8").splitlines()


@pytest.fixture
def operator() -> Iterator[dict[str, object]]:
    """ログイン済みのクライアントと、API キー、セッション ID を用意する。"""
    ensure_feature()
    user_id = insert_user(unique("room_log"))
    assign_feature(user_id)
    session_id = str(insert_session(user_id, load_config().session_timeout_minutes))
    client = TestClient(room_app)
    client.cookies.set("session_id", session_id)
    key = "rk_" + unique("k") + "_secretsecretsecret"
    insert_api_key(user_id, key)
    yield {"client": client, "user_id": user_id, "session_id": session_id, "key": key}
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM room.room_schedules WHERE created_by_user_id = %s", (user_id,))


def _exercise_everything(op: dict[str, object], switchbot: FakeSwitchBot) -> str:
    """全種類の操作を、成功と失敗の両方で実行する。使った存在しない API キーを返す。"""
    client: TestClient = op["client"]  # type: ignore[assignment]
    key = str(op["key"])
    bad_key = "rk_" + unique("bad") + "_notregistered"

    # 認証の失敗（API キー・Cookie）
    TestClient(room_app).get("/state", headers={"Authorization": f"Bearer {bad_key}"})
    TestClient(room_app).get("/state")

    # 状態取得（一部の機器の失敗を含む）
    switchbot.statuses[ID_BEDSIDE] = failure()
    client.get("/state")
    switchbot.statuses[ID_BEDSIDE] = {"power": "off"}

    # 個別切替: 画面の利用者（成功・入力不正・SwitchBot の失敗）、API の利用者
    client.put("/devices/indirect_light/state", json={"state": "off"})
    client.put("/devices/front_door/state", json={"state": "on"})
    switchbot.command_errors[ID_INDOOR] = failure()
    client.put("/devices/indoor_speaker/state", json={"state": "on"})
    del switchbot.command_errors[ID_INDOOR]
    TestClient(room_app).put(
        "/devices/front_door/state",
        json={"state": "unlocked"},
        headers={"Authorization": f"Bearer {key}"},
    )

    # 一括切替（成功・一部失敗・対象なし）
    client.post("/scenes/ceiling_light")
    switchbot.command_errors[ID_BEDSIDE] = failure()
    client.post("/scenes/indoor_speaker")
    del switchbot.command_errors[ID_BEDSIDE]
    client.post("/scenes/no_such_scene")

    # 定期実行の管理（登録・不正入力・変更・有効無効・削除・対象なし）
    created = client.post(
        "/schedules", json={"condition": "daily", "run_time": "07:00", "scene": "out"}
    ).json()
    client.post("/schedules", json={"condition": "monthly", "run_time": "07:00", "scene": "out"})
    client.get("/schedules")
    client.put(
        f"/schedules/{created['id']}",
        json={"condition": "weekdays", "weekdays": [6, 7], "run_time": "08:00", "scene": "out"},
    )
    client.put(f"/schedules/{created['id']}/enabled", json={"is_enabled": False})
    client.put("/schedules/999999999/enabled", json={"is_enabled": True})
    client.delete(f"/schedules/{created['id']}")

    # 定期実行ジョブ（実行する・実行しない）
    user_id = int(op["user_id"])  # type: ignore[call-overload]
    from datetime import time

    due = repos.get_room_schedule(
        repos.insert_room_schedule(user_id, repos.ScheduleDefinition("daily", (), "none", "same", time(7, 0), "scene", "bedside_speaker", None, None), True)
    )
    skipped = repos.get_room_schedule(
        repos.insert_room_schedule(user_id, repos.ScheduleDefinition("daily", (), "none", "same", time(12, 0), "scene", "out", None, None), True)
    )
    assert due is not None and skipped is not None
    set_source("job")
    run_once(
        now=datetime(2026, 10, 1, 7, 0, 30, tzinfo=JST),
        schedules=[due, skipped],
    )
    set_source("api")
    return bad_key


def test_すべての行がタイムスタンプ_区分_出力元_メッセージの形(
    operator: dict[str, object], switchbot: FakeSwitchBot, log_dir: Path
) -> None:
    _exercise_everything(operator, switchbot)
    lines = _lines(log_dir)
    assert len(lines) > 30
    assert [line for line in lines if not LINE.match(line)] == []


def test_秘密情報がログに出ない(
    operator: dict[str, object], switchbot: FakeSwitchBot, log_dir: Path
) -> None:
    bad_key = _exercise_everything(operator, switchbot)
    log = "\n".join(_lines(log_dir))
    key = str(operator["key"])
    secrets = {
        "SwitchBot のトークン": TEST_TOKEN,
        "SwitchBot のシークレット": TEST_SECRET,
        "機器の識別子（間接照明）": ID_INDIRECT,
        "機器の識別子（屋内スピーカー）": ID_INDOOR,
        "機器の識別子（枕元スピーカー）": ID_BEDSIDE,
        "機器の識別子（玄関ドア）": ID_DOOR,
        "セッション ID": str(operator["session_id"]),
        "API キー全体": key,
        "API キーのハッシュ": hash_api_key(key),
        "存在しない API キー全体": bad_key,
        "存在しない API キーのハッシュ": hash_api_key(bad_key),
    }
    leaked = [name for name, value in secrets.items() if value in log]
    assert leaked == []
    # API キーは識別用の先頭部分だけ出してよい
    assert key[:12] in log


def test_機器の変更に対象_変更後の状態_主体_成否_理由が残る(
    operator: dict[str, object], switchbot: FakeSwitchBot, log_dir: Path
) -> None:
    _exercise_everything(operator, switchbot)
    log = "\n".join(_lines(log_dir))

    # 個別切替: 画面の利用者の成功
    assert "機器切替要求 device=indirect_light target=off 主体=画面の利用者" in log
    assert "機器切替成功 device=indirect_light target=off 主体=画面の利用者" in log
    # 個別切替: 入力不正（理由）
    assert "機器切替失敗 device=front_door target=on 理由=その機器で取り得ない状態" in log
    # 個別切替: SwitchBot の失敗（主体と理由）
    assert "機器切替失敗 device=indoor_speaker target=on 主体=画面の利用者 理由=API エラー statusCode=190" in log
    # 個別切替: API の利用者
    assert "機器切替成功 device=front_door target=unlocked 主体=API の利用者" in log

    # 一括切替: 機器ごとの対象・変更後の状態・主体・結果
    assert "一括切替 scene=indoor_speaker device=indoor_speaker target=on 主体=画面の利用者 結果=success" in log
    assert "一括切替 scene=indoor_speaker device=bedside_speaker target=off 主体=画面の利用者 結果=failure" in log
    assert "一括切替 scene=ceiling_light device=ceiling_light target=on 判断=未実装のため何も指示しない" in log
    assert "一括切替結果 scene=indoor_speaker 主体=画面の利用者 全体=partial" in log
    assert "一括切替失敗 scene=no_such_scene 理由=一括切替が存在しない" in log


def test_定期実行の判定と実行が主体つきで残る(
    operator: dict[str, object], switchbot: FakeSwitchBot, log_dir: Path
) -> None:
    _exercise_everything(operator, switchbot)
    lines = _lines(log_dir)
    job_lines = [line for line in lines if "[job]" in line]
    text = "\n".join(job_lines)

    assert "定期実行の判定開始 判定時刻=2026-10-01 07:00:30" in text
    assert re.search(r"判断=実行する action=scene scene=bedside_speaker 条件=daily 祝日の扱い=none 実行日の取り方=same 時刻=07:00 実行日=2026-10-01 基準日=2026-10-01", text)
    assert re.search(r"判断=実行しない 理由=時刻が範囲外", text)
    # 定期実行による機器の変更の主体
    assert "一括切替 scene=bedside_speaker device=bedside_speaker target=on 主体=定期実行 結果=success" in text
    assert "定期実行の結果" in text
    assert "定期実行の判定終了 実行=1 実行しない=1" in text
    # API のログと出力元が混ざらない
    assert not any("[job]" in line and "状態取得要求" in line for line in lines)


def test_認証と定期実行の管理の入力_判断_理由が残る(
    operator: dict[str, object], switchbot: FakeSwitchBot, log_dir: Path
) -> None:
    bad_key = _exercise_everything(operator, switchbot)
    log = "\n".join(_lines(log_dir))

    assert f"API キー認証失敗 prefix={bad_key[:12]} 理由=該当なし" in log
    assert "認証失敗 理由=未ログイン" in log
    assert "API キー認証成功" in log
    assert "状態取得要求" in log
    assert "状態取得失敗 device=bedside_speaker" in log
    assert "定期実行の登録要求" in log and "定期実行の登録成功" in log
    assert "定期実行の入力不正 理由=実行条件が不正" in log
    assert "定期実行の変更成功" in log
    assert "定期実行の有効／無効の切替成功" in log
    assert "定期実行の有効／無効の切替失敗 id=999999999 理由=対象なし" in log
    assert "定期実行の削除成功" in log
