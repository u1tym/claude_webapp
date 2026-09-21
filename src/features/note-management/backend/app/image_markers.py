"""画像のマーカー・表示倍率の検証（api-design.md「Marker」）。"""

from __future__ import annotations

from typing import Any

from app.errors import InvalidInputError

MAX_MARKERS = 100
MIN_SCALE = 0.25
MAX_SCALE = 4.0
MARKER_MESSAGE = "マーカーが正しくありません"
SCALE_MESSAGE = "表示倍率は 25〜400% の範囲で指定してください"


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_scale(value: Any) -> float:
    if not _is_number(value) or not (MIN_SCALE <= float(value) <= MAX_SCALE):
        raise InvalidInputError(SCALE_MESSAGE, reason=f"倍率が範囲外 value={value!r}")
    return float(value)


def validate_markers(markers: Any) -> list[dict[str, Any]]:
    """検証して、保存する形（id・kind・x・y・text、番号マーカーは number）に整える。"""
    if not isinstance(markers, list):
        raise InvalidInputError(MARKER_MESSAGE, reason="markers が配列でない")
    if len(markers) > MAX_MARKERS:
        raise InvalidInputError(f"マーカーは {MAX_MARKERS} 個までです", reason=f"マーカー数={len(markers)}")

    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for marker in markers:
        if not isinstance(marker, dict):
            raise InvalidInputError(MARKER_MESSAGE, reason="マーカーがオブジェクトでない")
        marker_id = marker.get("id")
        kind = marker.get("kind")
        x, y = marker.get("x"), marker.get("y")
        text = marker.get("text", "")
        number = marker.get("number")
        if not isinstance(marker_id, str) or not (1 <= len(marker_id) <= 64):
            raise InvalidInputError(MARKER_MESSAGE, reason="マーカー id が不正")
        if marker_id in seen:
            raise InvalidInputError(MARKER_MESSAGE, reason=f"マーカー id の重複 id={marker_id}")
        seen.add(marker_id)
        if kind not in ("house", "number"):
            raise InvalidInputError(MARKER_MESSAGE, reason=f"kind が不正 kind={kind!r}")
        if not (_is_number(x) and _is_number(y) and 0 <= x <= 1 and 0 <= y <= 1):
            raise InvalidInputError(MARKER_MESSAGE, reason="位置が範囲外")
        if not isinstance(text, str):
            raise InvalidInputError(MARKER_MESSAGE, reason="text が文字列でない")
        item: dict[str, Any] = {"id": marker_id, "kind": kind, "x": x, "y": y, "text": text}
        if kind == "house":
            if number is not None:
                raise InvalidInputError(MARKER_MESSAGE, reason="家マーカーに番号がある")
        else:
            if not isinstance(number, int) or isinstance(number, bool) or number < 1:
                raise InvalidInputError(MARKER_MESSAGE, reason="番号マーカーの番号が不正")
            item["number"] = number
        result.append(item)
    return result
