from __future__ import annotations

from app.logger import setup_logging, write
from app.services.notice_service import run_once


def main() -> None:
    setup_logging()
    try:
        run_once()
    except Exception as exc:
        write("ERR", f"想定外の失敗 type={type(exc).__name__}")
        raise


if __name__ == "__main__":
    main()
