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
        # 指示のあと、状態に反映されるまでに、状態の取得が何回「古い値」を返すか（実機の反映の遅れの再現用）
        self.lag_reads: dict[str, int] = {}
        # 状態の取得を、先頭から何回失敗させるか（一時的な取得の失敗の再現用）
        self.status_failures: dict[str, int] = {}
        # 呼び出しの順序（"command" / "status"。テストが "sleep" も足せる）
        self.events: list[str] = []
        self._pending: dict[str, tuple[str, int]] = {}

    def _apply(self, device_id: str, command: str) -> None:
        body = self.statuses.get(device_id)
        if not isinstance(body, dict):
            return
        if command in ("turnOn", "turnOff"):
            body["power"] = "on" if command == "turnOn" else "off"
        elif command in ("lock", "unlock"):
            body["lockState"] = "locked" if command == "lock" else "unlocked"

    def get_status(self, device_id: str) -> dict[str, Any]:
        self.events.append("status")
        self.status_calls.append(device_id)
        failures = self.status_failures.get(device_id, 0)
        if failures > 0:
            self.status_failures[device_id] = failures - 1
            raise failure()
        pending = self._pending.get(device_id)
        if pending is not None:
            command, reads_left = pending
            if reads_left > 0:
                self._pending[device_id] = (command, reads_left - 1)  # まだ古い値を返す
            else:
                self._apply(device_id, command)
                del self._pending[device_id]
        result = self.statuses[device_id]
        if isinstance(result, Exception):
            raise result
        return dict(result)

    def send_command(self, device_id: str, command: str) -> None:
        self.events.append("command")
        self.commands.append((device_id, command))
        error = self.command_errors.get(device_id)
        if error is not None:
            raise error
        if device_id in self.fail_status_after_command:
            self.statuses[device_id] = failure()
            return
        if not self.apply_commands:
            return
        lag = self.lag_reads.get(device_id, 0)
        if lag > 0:
            self._pending[device_id] = (command, lag)
            return
        # 成功したら、状態も変わったものとして扱う
        self._apply(device_id, command)


def failure() -> SwitchBotError:
    return SwitchBotError("API エラー statusCode=190")
