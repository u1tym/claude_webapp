from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture(autouse=True)
def log_dir(tmp_path: Path) -> Path:
    from app.logger import close_logging, setup_logging

    directory = tmp_path / "log"
    setup_logging(log_dir=directory)
    yield directory
    close_logging()
