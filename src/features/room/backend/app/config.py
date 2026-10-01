from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BACKEND_DIR / ".env"

# 機能マスタの識別子（利用可否の判定に使う）
FEATURE_ID = "room"

# 設定値の既定
DEFAULT_SCHEDULE_GRACE_MINUTES = 5
DEFAULT_SWITCHBOT_TIMEOUT_SECONDS = 10
# 機器を切り替えたあと、実機の反映を待って状態を取り直す最大の時間（秒）。0 は待たない
DEFAULT_SETTLE_SECONDS = 5.0


def _loopback_aliases(origins: list[str]) -> list[str]:
    """localhost / 127.0.0.1 / [::1] を相互に許可オリジンへ加える。"""
    extra: list[str] = []
    for origin in origins:
        extra.append(origin)
        if "://localhost" in origin:
            extra.append(origin.replace("://localhost", "://127.0.0.1", 1))
            extra.append(origin.replace("://localhost", "://[::1]", 1))
        elif "://127.0.0.1" in origin:
            extra.append(origin.replace("://127.0.0.1", "://localhost", 1))
            extra.append(origin.replace("://127.0.0.1", "://[::1]", 1))
        elif "://[::1]" in origin:
            extra.append(origin.replace("://[::1]", "://localhost", 1))
            extra.append(origin.replace("://[::1]", "://127.0.0.1", 1))
    seen: set[str] = set()
    unique: list[str] = []
    for origin in extra:
        if origin not in seen:
            seen.add(origin)
            unique.append(origin)
    return unique


def _positive_int(
    values: dict[str, str | None],
    key: str,
    default: int,
    warnings: list[str],
) -> int:
    """正の整数として読む。未設定・空は既定。不正値は既定にして警告を残す。"""
    raw = (values.get(key) or "").strip()
    if not raw:
        return default
    try:
        number = int(raw)
    except ValueError:
        number = 0
    if number <= 0:
        warnings.append(f"設定値が不正のため既定を使用 name={key} 既定={default}")
        return default
    return number


def _non_negative_float(
    values: dict[str, str | None],
    key: str,
    default: float,
    warnings: list[str],
) -> float:
    """0 以上の数として読む（0 を許す）。未設定・空は既定。不正値は既定にして警告を残す。"""
    raw = (values.get(key) or "").strip()
    if not raw:
        return default
    try:
        number = float(raw)
    except ValueError:
        number = -1.0
    if not number >= 0 or number == float("inf"):
        warnings.append(f"設定値が不正のため既定を使用 name={key} 既定={default}")
        return default
    return number


@dataclass(frozen=True)
class Config:
    db_server: str
    db_name: str
    db_port: int
    db_username: str
    db_password: str
    cors_origins: list[str]
    session_timeout_minutes: int
    debug_user: str | None
    log_max_bytes: int
    log_backup_count: int
    # SwitchBot の認証情報と機器の識別子（コード・画面・応答・ログに出さない）
    switchbot_token: str
    switchbot_secret: str
    device_indirect_light_id: str
    device_indoor_speaker_id: str
    device_bedside_speaker_id: str
    device_front_door_id: str
    switchbot_timeout_seconds: int
    # 切替のあと、実機の反映を待って状態を取り直す最大の時間（秒）
    switch_settle_seconds: float
    schedule_grace_minutes: int
    # 設定値の読み取りで不正値を既定にした判断（起動時にログへ出す）
    warnings: tuple[str, ...] = ()


def load_config(env_path: Path | None = None) -> Config:
    values = dotenv_values(env_path if env_path is not None else ENV_PATH)
    warnings: list[str] = []

    cors_raw = values.get("CORS_ORIGINS") or ""
    origins = [part.strip() for part in cors_raw.split(",") if part.strip()]
    origins = _loopback_aliases(origins)
    debug = (values.get("DEBUG_USER") or "").strip() or None

    return Config(
        db_server=values.get("Server") or "localhost",
        db_name=values.get("Database") or "tstdb",
        db_port=int(values.get("Port") or "5432"),
        db_username=values.get("Username") or "tstuser",
        db_password=values.get("Password") or "",
        cors_origins=origins,
        session_timeout_minutes=int(values.get("SESSION_TIMEOUT_MINUTES") or "30"),
        debug_user=debug,
        log_max_bytes=int(values.get("LOG_MAX_BYTES") or "10485760"),
        log_backup_count=int(values.get("LOG_BACKUP_COUNT") or "5"),
        switchbot_token=(values.get("SWITCHBOT_TOKEN") or "").strip(),
        switchbot_secret=(values.get("SWITCHBOT_SECRET") or "").strip(),
        device_indirect_light_id=(values.get("ROOM_DEVICE_INDIRECT_LIGHT_ID") or "").strip(),
        device_indoor_speaker_id=(values.get("ROOM_DEVICE_INDOOR_SPEAKER_ID") or "").strip(),
        device_bedside_speaker_id=(values.get("ROOM_DEVICE_BEDSIDE_SPEAKER_ID") or "").strip(),
        device_front_door_id=(values.get("ROOM_DEVICE_FRONT_DOOR_ID") or "").strip(),
        switchbot_timeout_seconds=_positive_int(
            values,
            "SWITCHBOT_TIMEOUT_SECONDS",
            DEFAULT_SWITCHBOT_TIMEOUT_SECONDS,
            warnings,
        ),
        switch_settle_seconds=_non_negative_float(
            values, "ROOM_SETTLE_SECONDS", DEFAULT_SETTLE_SECONDS, warnings
        ),
        schedule_grace_minutes=_positive_int(
            values,
            "ROOM_SCHEDULE_GRACE_MINUTES",
            DEFAULT_SCHEDULE_GRACE_MINUTES,
            warnings,
        ),
        warnings=tuple(warnings),
    )
