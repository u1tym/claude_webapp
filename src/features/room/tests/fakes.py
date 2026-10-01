from __future__ import annotations

from typing import Any

from app.switchbot.client import SwitchBotError

# テスト用の機器識別子（実機の識別子ではない）。応答・ログに出ないことの確認にも使う
ID_INDIRECT = "TESTID-INDIRECT"
ID_INDOOR = "TESTID-INDOOR"
ID_BEDSIDE = "TESTID-BEDSIDE"
ID_DOOR = "TESTID-DOOR"
TEST_TOKEN = "test-token-value"
TEST_SECRET = "test-secret-value"


class FakeSwitchBot:
    """SwitchBot の代わりをするテスト用のクライアント。呼び出しを記録する。"""

    def __init__(self) -> None:
        self.statuses: dict[str, dict[str, Any] | Exception] = {
            ID_INDIRECT: {"power": "on"},
            ID_INDOOR: {"power": "off"},
            ID_BEDSIDE: {"power": "off"},
            ID_DOOR: {"lockState": "locked", "battery": 35},
        }
        self.command_errors: dict[str, Exception] = {}
        self.status_calls: list[str] = []
        self.commands: list[tuple[str, str]] = []
        # False なら、指示が成功しても機器の状態は変わらない（食い違いの再現用）
        self.apply_commands = True
        # 指示のあとに状態の取得を失敗させたい機器（取得し直しの失敗の再現用）
        self.fail_status_after_command: set[str] = set()

    def get_status(self, device_id: str) -> dict[str, Any]:
        self.status_calls.append(device_id)
        result = self.statuses[device_id]
        if isinstance(result, Exception):
            raise result
        return dict(result)

    def send_command(self, device_id: str, command: str) -> None:
        self.commands.append((device_id, command))
        error = self.command_errors.get(device_id)
        if error is not None:
            raise error
        if device_id in self.fail_status_after_command:
            self.statuses[device_id] = failure()
            return
        # 成功したら、状態も変わったものとして扱う
        body = self.statuses.get(device_id)
        if self.apply_commands and isinstance(body, dict):
            if command in ("turnOn", "turnOff"):
                body["power"] = "on" if command == "turnOn" else "off"
            elif command in ("lock", "unlock"):
                body["lockState"] = "locked" if command == "lock" else "unlocked"


def failure() -> SwitchBotError:
    return SwitchBotError("API エラー statusCode=190")
