"""定期実行ジョブ。`python -m app.jobs` で 1 回判定して終了する。

繰り返しは、タスクスケジューラなどで毎分起動して行う。HTTP サーバは使わない。
"""

from __future__ import annotations

import sys

from app.config import load_config
from app.logger import set_source, setup_logging, write, write_config_warnings
from app.services import runner_service


def main() -> int:
    """判定と実行を 1 回行い、終了コードを返す（0 = 正常、1 = 想定外の失敗）。"""
    setup_logging()
    set_source("job")
    write_config_warnings(load_config().warnings)
    try:
        runner_service.run_once()
    except Exception as exc:  # 想定外の失敗。内部情報はログにだけ残す
        write("ERR", f"定期実行ジョブの失敗 理由={type(exc).__name__}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
