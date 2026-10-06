from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests

from app.switchbot.client import SwitchBotClient, SwitchBotError, make_sign

SECRET_DEVICE_ID = "SECRETDEVICEID"


def _response(payload: dict[str, Any], status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload
    return resp


def test_署名は仕様どおり() -> None:
    expected = (
        base64.b64encode(hmac.new(b"secret", b"tokentnonce", hashlib.sha256).digest())
        .decode()
        .upper()
    )
    assert make_sign("token", "secret", "t", "nonce") == expected


def test_認証情報が空ならエラー() -> None:
    with pytest.raises(ValueError):
        SwitchBotClient("", "")


def test_リクエストごとに署名ヘッダを付け直す() -> None:
    payload = {"statusCode": 100, "message": "success", "body": {"power": "on"}}
    client = SwitchBotClient("tok", "sec", timeout_seconds=7)
    with patch("app.switchbot.client.requests.request", return_value=_response(payload)) as m:
        client.get_status("ABC")
        client.get_status("ABC")
    first, second = m.call_args_list
    assert {"Authorization", "sign", "t", "nonce"} <= set(first.kwargs["headers"])
    assert first.kwargs["headers"]["nonce"] != second.kwargs["headers"]["nonce"]
    assert first.kwargs["timeout"] == 7


def test_状態取得はGETでbodyを返す() -> None:
    payload = {"statusCode": 100, "message": "success", "body": {"power": "on"}}
    with patch("app.switchbot.client.requests.request", return_value=_response(payload)) as m:
        body = SwitchBotClient("tok", "sec").get_status("ABC")
    assert body == {"power": "on"}
    assert m.call_args.args[0] == "GET"
    assert m.call_args.args[1].endswith("/devices/ABC/status")


def test_コマンド送信はPOSTでペイロードを送る() -> None:
    payload = {"statusCode": 100, "message": "success", "body": {}}
    with patch("app.switchbot.client.requests.request", return_value=_response(payload)) as m:
        SwitchBotClient("tok", "sec").send_command("ABC", "turnOn")
    assert m.call_args.args[0] == "POST"
    assert m.call_args.args[1].endswith("/devices/ABC/commands")
    assert m.call_args.kwargs["json"] == {
        "command": "turnOn",
        "parameter": "default",
        "commandType": "command",
    }


def test_値つきのコマンドは_parameterに値を送る() -> None:
    payload = {"statusCode": 100, "message": "success", "body": {}}
    with patch("app.switchbot.client.requests.request", return_value=_response(payload)) as m:
        SwitchBotClient("tok", "sec").send_command("ABC", "setBrightness", "80")
    assert m.call_args.kwargs["json"] == {
        "command": "setBrightness",
        "parameter": "80",
        "commandType": "command",
    }


def test_statusCodeが100以外ならエラー() -> None:
    payload = {"statusCode": 190, "message": "device internal error", "body": {}}
    with patch("app.switchbot.client.requests.request", return_value=_response(payload)):
        with pytest.raises(SwitchBotError, match="190"):
            SwitchBotClient("tok", "sec").get_status("ABC")


def test_HTTPエラーならエラー() -> None:
    with patch("app.switchbot.client.requests.request", return_value=_response({}, status=401)):
        with pytest.raises(SwitchBotError, match="401"):
            SwitchBotClient("tok", "sec").get_status("ABC")


def test_通信失敗のメッセージに機器の識別子を含めない() -> None:
    boom = requests.ConnectionError(f"https://api/devices/{SECRET_DEVICE_ID}/status failed")
    with patch("app.switchbot.client.requests.request", side_effect=boom):
        with pytest.raises(SwitchBotError) as info:
            SwitchBotClient("tok", "sec").get_status(SECRET_DEVICE_ID)
    assert SECRET_DEVICE_ID not in str(info.value)
    assert "ConnectionError" in str(info.value)


def test_タイムアウトもエラーにまとめる() -> None:
    with patch("app.switchbot.client.requests.request", side_effect=requests.Timeout("x")):
        with pytest.raises(SwitchBotError, match="Timeout"):
            SwitchBotClient("tok", "sec").get_status("ABC")


def test_自動で再試行しない() -> None:
    with patch("app.switchbot.client.requests.request", side_effect=requests.Timeout("x")) as m:
        with pytest.raises(SwitchBotError):
            SwitchBotClient("tok", "sec").send_command("ABC", "turnOn")
    assert m.call_count == 1
