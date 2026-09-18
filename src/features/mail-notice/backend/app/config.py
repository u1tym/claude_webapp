from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path

from dotenv import dotenv_values


BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BACKEND_DIR / ".env"

DEFAULT_LEAD_MINUTES = 3
DEFAULT_DAY_TIME = time(9, 0)
DEFAULT_LOOKBACK_DAYS = 30


@dataclass(frozen=True)
class Config:
    db_server: str
    db_name: str
    db_port: int
    db_username: str
    db_password: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_from: str
    notice_lead_minutes: int
    notice_day_time: time
    notice_lookback_days: int
    log_max_bytes: int
    log_backup_count: int
    setting_warnings: tuple[str, ...]


def _positive_int(raw: str | None, default: int, name: str, warnings: list[str]) -> int:
    text = (raw or "").strip()
    if text == "":
        return default
    if not text.isdigit() or int(text) <= 0:
        warnings.append(f"設定値不正 {name}={text} 既定={default} を使用")
        return default
    return int(text)


def _hhmm(raw: str | None, default: time, name: str, warnings: list[str]) -> time:
    text = (raw or "").strip()
    if text == "":
        return default
    try:
        parsed = datetime.strptime(text, "%H:%M").time()
    except ValueError:
        warnings.append(f"設定値不正 {name}={text} 既定={default.strftime('%H:%M')} を使用")
        return default
    return parsed


def load_config() -> Config:
    values = dotenv_values(ENV_PATH)
    warnings: list[str] = []
    port_raw = (values.get("SMTP_PORT") or "587").strip()
    try:
        smtp_port = int(port_raw)
    except ValueError:
        smtp_port = 587
        warnings.append(f"設定値不正 SMTP_PORT={port_raw} 既定=587 を使用")
    return Config(
        db_server=values.get("Server") or "localhost",
        db_name=values.get("Database") or "tstdb",
        db_port=int(values.get("Port") or "5432"),
        db_username=values.get("Username") or "tstuser",
        db_password=values.get("Password") or "",
        smtp_host=(values.get("SMTP_HOST") or "").strip(),
        smtp_port=smtp_port,
        smtp_username=(values.get("SMTP_USERNAME") or "").strip(),
        smtp_password=values.get("SMTP_PASSWORD") or "",
        smtp_from=(values.get("SMTP_FROM") or "").strip(),
        notice_lead_minutes=_positive_int(
            values.get("NOTICE_LEAD_MINUTES"),
            DEFAULT_LEAD_MINUTES,
            "NOTICE_LEAD_MINUTES",
            warnings,
        ),
        notice_day_time=_hhmm(
            values.get("NOTICE_DAY_TIME"),
            DEFAULT_DAY_TIME,
            "NOTICE_DAY_TIME",
            warnings,
        ),
        notice_lookback_days=_positive_int(
            values.get("NOTICE_LOOKBACK_DAYS"),
            DEFAULT_LOOKBACK_DAYS,
            "NOTICE_LOOKBACK_DAYS",
            warnings,
        ),
        log_max_bytes=int(values.get("LOG_MAX_BYTES") or "10485760"),
        log_backup_count=int(values.get("LOG_BACKUP_COUNT") or "5"),
        setting_warnings=tuple(warnings),
    )
