from __future__ import annotations

import subprocess
import sys

from app.config import load_config
from app.logger import safe_text, write


def run_ping(host: str, timeout_seconds: int) -> tuple[bool, str]:
    timeout = max(1, timeout_seconds)
    if sys.platform == "win32":
        command = ["ping", "-n", "1", "-w", str(timeout * 1000), host]
    else:
        command = ["ping", "-c", "1", "-W", str(timeout), host]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout + 2,
        )
    except subprocess.TimeoutExpired:
        return False, "pingタイムアウト"
    except OSError as exc:
        return False, f"ping実行失敗 type={type(exc).__name__}"
    if completed.returncode == 0:
        return True, "応答あり"
    return False, f"応答なし code={completed.returncode}"


def check_power_status() -> bool:
    cfg = load_config()
    is_up, reason = run_ping(cfg.ping_host, cfg.ping_timeout_seconds)
    write(
        "INF" if is_up else "WRN",
        f"状態判定 ping_host={safe_text(cfg.ping_host)}"
        f" timeout={cfg.ping_timeout_seconds} is_up={str(is_up).lower()} 理由={reason}",
    )
    return is_up
