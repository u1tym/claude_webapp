from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.logger import (
    close_logging,
    set_source,
    setup_logging,
    write,
    write_config_warnings,
)

LINE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} (INF|WRN|ERR|DBG) \[(api|job)\] .+$")


def _lines(log_dir: Path) -> list[str]:
    return (log_dir / "room.log").read_text(encoding="utf-8").splitlines()


def test_ログ1行はタイムスタンプ_区分_出力元_メッセージの順(log_dir: Path) -> None:
    write("INF", "テスト")
    lines = _lines(log_dir)
    assert len(lines) == 1
    assert LINE.match(lines[0])


def test_出力元を切り替えられる(log_dir: Path) -> None:
    set_source("job")
    write("WRN", "ジョブのログ")
    assert " WRN [job] ジョブのログ" in _lines(log_dir)[-1]


def test_改行は空白にして1行に収める(log_dir: Path) -> None:
    write("INF", "a\nb\rc")
    assert len(_lines(log_dir)) == 1
    assert _lines(log_dir)[0].endswith("a b c")


def test_設定の警告をWRNで残す(log_dir: Path) -> None:
    write_config_warnings(("設定値が不正のため既定を使用 name=X 既定=5",))
    assert " WRN [api] 設定値が不正のため既定を使用 name=X 既定=5" in _lines(log_dir)[-1]


def test_サイズでローテーションする(tmp_path: Path) -> None:
    directory = tmp_path / "rot"
    setup_logging(log_dir=directory, max_bytes=200, backup_count=2)
    try:
        for i in range(30):
            write("INF", f"ローテーション確認 {i}")
        names = sorted(p.name for p in directory.iterdir())
        assert "room.log" in names
        assert "room.log.1" in names
        # 世代数は backup_count まで
        assert "room.log.3" not in names
    finally:
        close_logging()


def test_アプリが起動し_存在しないパスは404のJSON() -> None:
    from app.main import create_app

    client = TestClient(create_app())
    resp = client.get("/no-such-path")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Not Found"}


def test_許可オリジン以外はCORSヘッダを返さない() -> None:
    from app.main import create_app

    client = TestClient(create_app())
    resp = client.get("/no-such-path", headers={"Origin": "http://evil.example.com"})
    assert "access-control-allow-origin" not in resp.headers
