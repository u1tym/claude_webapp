from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

BACKEND_DIR = Path(__file__).resolve().parent.parent
# 既定は backend/.env。RECIPE_MANAGEMENT_ENV_FILE で別の設定ファイルを指定できる
# （例: 移行プログラムの移行先を、本番の DB にする）。
ENV_PATH = Path(os.environ.get("RECIPE_MANAGEMENT_ENV_FILE") or BACKEND_DIR / ".env")

FEATURE_ID = "recipe-management"


def _loopback_aliases(origins: list[str]) -> list[str]:
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


def load_config() -> Config:
    values = dotenv_values(ENV_PATH)

    def db_value(*names: str) -> str | None:
        # テンプレートの名前（DB_SERVER など）と、他機能の .env の名前（Server など）の両方を受け付ける
        for name in names:
            if values.get(name):
                return values.get(name)
        return None

    cors_raw = values.get("CORS_ORIGINS") or ""
    origins = [part.strip() for part in cors_raw.split(",") if part.strip()]
    origins = _loopback_aliases(origins)
    debug = (values.get("DEBUG_USER") or "").strip() or None
    return Config(
        db_server=db_value("DB_SERVER", "Server") or "localhost",
        db_name=db_value("DB_DATABASE", "Database") or "tstdb",
        db_port=int(db_value("DB_PORT", "Port") or "5432"),
        db_username=db_value("DB_USERNAME", "Username") or "tstuser",
        db_password=db_value("DB_PASSWORD", "Password") or "",
        cors_origins=origins,
        session_timeout_minutes=int(values.get("SESSION_TIMEOUT_MINUTES") or "30"),
        debug_user=debug,
        log_max_bytes=int(values.get("LOG_MAX_BYTES") or "10485760"),
        log_backup_count=int(values.get("LOG_BACKUP_COUNT") or "5"),
    )
