from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture
def switchbot(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """SwitchBot をテスト用の偽物に差し替える（実機を呼ばない）。"""
    import dataclasses

    from app.config import load_config
    from app.services import device_service
    from fakes import (
        ID_BEDSIDE,
        ID_DOOR,
        ID_INDIRECT,
        ID_INDOOR,
        TEST_SECRET,
        TEST_TOKEN,
        FakeSwitchBot,
    )

    cfg = dataclasses.replace(
        load_config(),
        switchbot_token=TEST_TOKEN,
        switchbot_secret=TEST_SECRET,
        device_indirect_light_id=ID_INDIRECT,
        device_indoor_speaker_id=ID_INDOOR,
        device_bedside_speaker_id=ID_BEDSIDE,
        device_front_door_id=ID_DOOR,
    )
    fake = FakeSwitchBot()
    monkeypatch.setattr(device_service, "load_config", lambda: cfg)
    monkeypatch.setattr(device_service, "build_client", lambda _cfg=None: fake)
    return fake


@pytest.fixture(autouse=True)
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """切替のあとの反映待ちを、実際には待たず、待とうとした秒数を記録する。"""
    from app.services import device_service

    recorded: list[float] = []
    monkeypatch.setattr(device_service, "_sleep", recorded.append)
    return recorded


@pytest.fixture(autouse=True)
def log_dir(tmp_path: Path) -> Iterator[Path]:
    """テスト中のログを一時フォルダへ出す。"""
    from app.logger import close_logging, set_source, setup_logging

    directory = tmp_path / "log"
    setup_logging(log_dir=directory)
    set_source("api")
    yield directory
    close_logging()


@pytest.fixture(scope="session", autouse=True)
def cleanup_created_users() -> Iterator[None]:
    """実行の最後に、このテストが作ったユーザと、そのユーザに紐づくデータを片付ける。

    開発用 DB にテスト用のデータを積み残さないため。機能マスタ（public.features）の room は、
    実際の登録と区別できないので消さない。
    """
    yield
    from helpers import CREATED_USER_IDS

    if not CREATED_USER_IDS:
        return
    try:
        from app.db import get_conn

        ids = list(CREATED_USER_IDS)
        with get_conn() as conn, conn.cursor() as cur:
            # 外部キーの順（参照する側から）に消す
            cur.execute("DELETE FROM room.room_schedules WHERE created_by_user_id = ANY(%s)", (ids,))
            cur.execute("DELETE FROM public.api_keys WHERE user_id = ANY(%s)", (ids,))
            cur.execute("DELETE FROM public.sessions WHERE user_id = ANY(%s)", (ids,))
            cur.execute("DELETE FROM public.menu_assignments WHERE user_id = ANY(%s)", (ids,))
            cur.execute("DELETE FROM public.users WHERE id = ANY(%s)", (ids,))
    except Exception as exc:  # 後始末の失敗でテストの結果を変えない
        print(f"テスト用データの後始末に失敗しました: {type(exc).__name__}")
