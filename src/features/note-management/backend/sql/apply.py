"""sql/*.sql を番号順に適用する。backend/.env の接続情報（開発用 DB）を使う。

使い方（backend で venv を有効化してから）:
    python sql/apply.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.db import get_conn  # noqa: E402


def main() -> None:
    files = sorted(Path(__file__).resolve().parent.glob("[0-9][0-9]_*.sql"))
    with get_conn() as conn:
        with conn.cursor() as cur:
            for path in files:
                cur.execute(path.read_text(encoding="utf-8"))
                print(f"適用: {path.name}")


if __name__ == "__main__":
    main()
