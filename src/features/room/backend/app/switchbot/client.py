"""SwitchBot Web API v1.1 の最小クライアント。

`D:\\claude_code\\switchbot` の `switchbot_client.py` を元に、本機能へ複製したもの
（他フォルダの Python を import しない方針のため）。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
import uuid
from typing import Any, Protocol

import requests

BASE_URL = "https://api.switch-bot.com/v1.1"


class SwitchBotError(Exception):
    """SwitchBot への接続失敗・エラー応答。メッセージに認証情報や機器の識別子を含めない。"""


class SwitchBotApi(Protocol):
    """サービス層が使う SwitchBot の窓口（テストで差し替えるための型）。"""

    def get_status(self, device_id: str) -> dict[str, Any]: ...

    def send_command(self, device_id: str, command: str) -> None: ...


def make_sign(token: str, secret: str, t: str, nonce: str) -> str:
    """署名を生成する: Base64(HMAC-SHA256(secret, token + t + nonce)) の大文字。"""
    message = f"{token}{t}{nonce}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8").upper()


class SwitchBotClient:
    def __init__(self, token: str, secret: str, timeout_seconds: int = 10) -> None:
        if not token or not secret:
            raise ValueError("token と secret は必須です")
        self._token = token
        self._secret = secret
        self._timeout = timeout_seconds

    def _headers(self) -> dict[str, str]:
        # 署名はリクエストごとに timestamp(ms) と nonce を作り直す
        t = str(int(time.time() * 1000))
        nonce = str(uuid.uuid4())
        return {
            "Authorization": self._token,
            "sign": make_sign(self._token, self._secret, t, nonce),
            "t": t,
            "nonce": nonce,
            "Content-Type": "application/json; charset=utf8",
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """API を 1 回だけ呼ぶ（自動で再試行しない）。失敗は SwitchBotError にまとめる。"""
        try:
            resp = requests.request(
                method,
                f"{BASE_URL}{path}",
                headers=self._headers(),
                timeout=self._timeout,
                **kwargs,
            )
        except requests.RequestException as exc:
            # 例外の文字列には URL（機器の識別子）が入るため、型名だけを残す
            raise SwitchBotError(f"通信失敗 type={type(exc).__name__}") from None
        if resp.status_code >= 400:
            raise SwitchBotError(f"HTTP エラー status={resp.status_code}")
        try:
            data: dict[str, Any] = resp.json()
        except ValueError:
            raise SwitchBotError("応答が JSON でない") from None
        # HTTP 200 でも statusCode が 100 以外ならエラー
        if data.get("statusCode") != 100:
            raise SwitchBotError(f"API エラー statusCode={data.get('statusCode')}")
        body = data.get("body", {})
        return body if isinstance(body, dict) else {}

    def get_status(self, device_id: str) -> dict[str, Any]:
        """デバイスの状態を返す。"""
        return self._request("GET", f"/devices/{device_id}/status")

    def send_command(self, device_id: str, command: str) -> None:
        """デバイスへコマンドを送る（turnOn / turnOff / lock / unlock）。"""
        payload = {"command": command, "parameter": "default", "commandType": "command"}
        self._request("POST", f"/devices/{device_id}/commands", json=payload)
