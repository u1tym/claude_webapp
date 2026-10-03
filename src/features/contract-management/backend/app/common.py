from __future__ import annotations

from app.errors import InvalidInputError


def required_text(value: object, max_length: int | None = None) -> str:
    """前後の空白を除いて、空でない文字列にする。違反は入力不正。"""
    if not isinstance(value, str):
        raise InvalidInputError("文字列でない")
    text = value.strip()
    if text == "":
        raise InvalidInputError("空")
    if max_length is not None and len(text) > max_length:
        raise InvalidInputError("長すぎる")
    return text


def optional_text(value: object) -> str | None:
    """前後の空白を除く。None・空文字・空白のみは None にする。"""
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidInputError("文字列でない")
    text = value.strip()
    return text or None
