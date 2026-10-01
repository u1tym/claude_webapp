from __future__ import annotations

from pathlib import Path

from app.config import (
    DEFAULT_SCHEDULE_GRACE_MINUTES,
    DEFAULT_SWITCHBOT_TIMEOUT_SECONDS,
    load_config,
)


def _write_env(tmp_path: Path, body: str) -> Path:
    path = tmp_path / ".env"
    path.write_text(body, encoding="utf-8")
    return path


def test_未設定なら既定を使う(tmp_path: Path) -> None:
    cfg = load_config(_write_env(tmp_path, ""))
    assert cfg.schedule_grace_minutes == DEFAULT_SCHEDULE_GRACE_MINUTES == 5
    assert cfg.switchbot_timeout_seconds == DEFAULT_SWITCHBOT_TIMEOUT_SECONDS == 10
    assert cfg.debug_user is None
    assert cfg.warnings == ()


def test_空文字は既定でありログに残さない(tmp_path: Path) -> None:
    cfg = load_config(
        _write_env(tmp_path, "ROOM_SCHEDULE_GRACE_MINUTES=\nSWITCHBOT_TIMEOUT_SECONDS=\n")
    )
    assert cfg.schedule_grace_minutes == 5
    assert cfg.switchbot_timeout_seconds == 10
    assert cfg.warnings == ()


def test_正の整数なら設定値を使う(tmp_path: Path) -> None:
    cfg = load_config(
        _write_env(tmp_path, "ROOM_SCHEDULE_GRACE_MINUTES=10\nSWITCHBOT_TIMEOUT_SECONDS=3\n")
    )
    assert cfg.schedule_grace_minutes == 10
    assert cfg.switchbot_timeout_seconds == 3
    assert cfg.warnings == ()


def test_不正な猶予分は既定にして判断を残す(tmp_path: Path) -> None:
    for bad in ("0", "-1", "abc", "1.5"):
        cfg = load_config(_write_env(tmp_path, f"ROOM_SCHEDULE_GRACE_MINUTES={bad}\n"))
        assert cfg.schedule_grace_minutes == 5
        assert any("ROOM_SCHEDULE_GRACE_MINUTES" in w for w in cfg.warnings)


def test_不正なタイムアウトは既定にして判断を残す(tmp_path: Path) -> None:
    cfg = load_config(_write_env(tmp_path, "SWITCHBOT_TIMEOUT_SECONDS=0\n"))
    assert cfg.switchbot_timeout_seconds == 10
    assert any("SWITCHBOT_TIMEOUT_SECONDS" in w for w in cfg.warnings)


def test_警告に設定値や秘密情報を含めない(tmp_path: Path) -> None:
    cfg = load_config(
        _write_env(
            tmp_path,
            "SWITCHBOT_TOKEN=secret-token\nSWITCHBOT_SECRET=secret-secret\n"
            "ROOM_SCHEDULE_GRACE_MINUTES=bad\n",
        )
    )
    joined = " ".join(cfg.warnings)
    assert "secret-token" not in joined
    assert "secret-secret" not in joined


def test_CORSとSwitchBot設定を読む(tmp_path: Path) -> None:
    cfg = load_config(
        _write_env(
            tmp_path,
            "CORS_ORIGINS=http://localhost:5173\n"
            "SWITCHBOT_TOKEN=t\nSWITCHBOT_SECRET=s\n"
            "ROOM_DEVICE_INDIRECT_LIGHT_ID=A\nROOM_DEVICE_INDOOR_SPEAKER_ID=B\n"
            "ROOM_DEVICE_BEDSIDE_SPEAKER_ID=C\nROOM_DEVICE_FRONT_DOOR_ID=D\n"
            "DEBUG_USER=alice\n",
        )
    )
    assert "http://localhost:5173" in cfg.cors_origins
    assert "http://127.0.0.1:5173" in cfg.cors_origins
    assert (cfg.switchbot_token, cfg.switchbot_secret) == ("t", "s")
    assert cfg.device_indirect_light_id == "A"
    assert cfg.device_indoor_speaker_id == "B"
    assert cfg.device_bedside_speaker_id == "C"
    assert cfg.device_front_door_id == "D"
    assert cfg.debug_user == "alice"
