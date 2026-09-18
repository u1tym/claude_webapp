from __future__ import annotations

import subprocess
import sys
import threading

from app.config import BACKEND_DIR, load_config
from app.logger import safe_text, write

_lock = threading.Lock()


class StartBusyError(Exception):
    pass


class StartFailedError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def execute_wol(mac: str) -> int:
    script = BACKEND_DIR / "scripts" / "wol.py"
    completed = subprocess.run(
        [sys.executable, str(script), mac],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return completed.returncode


def run_start() -> None:
    cfg = load_config()
    mac = cfg.wol_mac
    acquired = _lock.acquire(blocking=False)
    if not acquired:
        write("WRN", f"起動処理拒否 mac={safe_text(mac)} 理由=実行中")
        raise StartBusyError()
    try:
        write("INF", f"起動処理開始 mac={safe_text(mac)}")
        try:
            code = execute_wol(mac)
        except (OSError, subprocess.TimeoutExpired) as exc:
            reason = f"type={type(exc).__name__}"
            write("WRN", f"起動処理失敗 mac={safe_text(mac)} 理由={reason}")
            raise StartFailedError(reason) from exc
        if code != 0:
            reason = f"終了コード={code}"
            write("WRN", f"起動処理失敗 mac={safe_text(mac)} 理由={reason}")
            raise StartFailedError(reason)
        write("INF", f"起動処理成功 mac={safe_text(mac)}")
    finally:
        _lock.release()
