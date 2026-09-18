from __future__ import annotations

import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Literal

from app.config import BACKEND_DIR, load_config

Level = Literal["INF", "WRN", "ERR", "DBG"]

LOG_NAME = "portal"
LOG_FILE = "portal.log"

_logger = logging.getLogger(LOG_NAME)
_logger.setLevel(logging.INFO)
_logger.propagate = False


def safe_text(value: str) -> str:
    return value.replace("\r", " ").replace("\n", " ")


def log_file_path(log_dir: Path | None = None) -> Path:
    directory = log_dir if log_dir is not None else BACKEND_DIR / "log"
    return directory / LOG_FILE


def close_logging() -> None:
    for handler in list(_logger.handlers):
        handler.close()
        _logger.removeHandler(handler)


def setup_logging(
    log_dir: Path | None = None,
    max_bytes: int | None = None,
    backup_count: int | None = None,
) -> Path:
    cfg = load_config()
    directory = log_dir if log_dir is not None else BACKEND_DIR / "log"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / LOG_FILE
    size = max_bytes if max_bytes is not None else cfg.log_max_bytes
    generations = backup_count if backup_count is not None else cfg.log_backup_count
    close_logging()
    handler = RotatingFileHandler(
        path,
        maxBytes=size,
        backupCount=generations,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(handler)
    return path


def write(level: Level, message: str) -> None:
    if not _logger.handlers:
        setup_logging()
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _logger.info("%s %s %s", stamp, level, message)
    for handler in _logger.handlers:
        handler.flush()
