"""運用手順書（README.md）が、設定値と運用の手順を、漏れなく載せていることの確認（T-020）。"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOM_DIR = Path(__file__).resolve().parents[1]
README = (ROOM_DIR / "README.md").read_text(encoding="utf-8")
ENV_EXAMPLE = (ROOM_DIR / "backend" / ".env.example").read_text(encoding="utf-8")
CONFIG = (ROOM_DIR / "backend" / "app" / "config.py").read_text(encoding="utf-8")


def _config_keys() -> list[str]:
    """config.py が .env から読む項目名。"""
    keys = re.findall(r'values\.get\("([A-Za-z_]+)"\)', CONFIG)
    keys += re.findall(r'_positive_int\(\s*values,\s*"([A-Za-z_]+)"', CONFIG)
    return sorted(set(keys))


def test_config_が読む項目を取り出せている() -> None:
    keys = _config_keys()
    # 取り出しが壊れて、空のまま検証が通ることを防ぐ
    assert len(keys) >= 17
    assert "SWITCHBOT_TOKEN" in keys and "ROOM_SCHEDULE_GRACE_MINUTES" in keys


@pytest.mark.parametrize("key", _config_keys())
def test_すべての設定項目が_READMEに載っている(key: str) -> None:
    assert key in README, f"README.md に {key} の説明がありません"


@pytest.mark.parametrize("key", _config_keys())
def test_すべての設定項目が_env_example_にある(key: str) -> None:
    assert re.search(rf"^{key}=", ENV_EXAMPLE, re.M), f".env.example に {key} がありません"


@pytest.mark.parametrize(
    "text",
    [
        # 起動
        "uvicorn app.main:app --port 8011",
        "python -m app.jobs",
        # タスクスケジューラ
        "Register-ScheduledTask",
        "New-ScheduledTaskTrigger",
        "-RepetitionInterval (New-TimeSpan -Minutes 1)",
        "-WorkingDirectory",
        "pythonw.exe",
        "Get-ScheduledTaskInfo",
        "Unregister-ScheduledTask",
        # ログ
        "backend/log/room.log",
        "LOG_MAX_BYTES",
        # 機能マスタ・割当
        "app.cli feature add room",
        "app.cli menu assign",
    ],
)
def test_運用の手順に必要なコマンドが載っている(text: str) -> None:
    assert text in README


def test_定期実行の実行しない理由が_すべて載っている() -> None:
    """ジョブが出す「実行しない」の理由（runner_service）を、トラブルの切り分けに載せている。"""
    runner = (ROOM_DIR / "backend" / "app" / "services" / "runner_service.py").read_text(
        encoding="utf-8"
    )
    for reason in ("無効", "時刻が範囲外", "条件に合わない", "実行済み"):
        assert reason in runner, f"runner_service に理由「{reason}」がありません（READMEと食い違い）"
        assert reason in README, f"README に理由「{reason}」の説明がありません"


def test_秘密情報の値を書いていない() -> None:
    # .env の実際の値（トークンなど）を、README に書き写していないこと
    env_path = ROOM_DIR / "backend" / ".env"
    if not env_path.exists():
        pytest.skip(".env がありません")
    for line in env_path.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        if key in {"SWITCHBOT_TOKEN", "SWITCHBOT_SECRET", "Password"} and len(value.strip()) >= 8:
            assert value.strip() not in README
