from __future__ import annotations


class NotFoundError(Exception):
    """対象（機器、一括切替、定期実行）が存在しない。"""


class InvalidInputError(Exception):
    """入力が不正。"""


class DeviceOperationError(Exception):
    """SwitchBot への指示に失敗した（接続できない、エラー応答）。"""
