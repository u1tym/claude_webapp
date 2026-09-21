"""行動予定の本文（JSON 文字列）の検証と正規化（api-design.md「行動予定の本文」）。"""

from __future__ import annotations

import json
from typing import Any

from app.errors import InvalidInputError

MESSAGE = "行動予定の内容が正しくありません"
_POINT_KEYS = {"place", "time", "arrive", "depart"}
_LEG_KEYS = {"memo", "note"}


def _fail(reason: str) -> InvalidInputError:
    return InvalidInputError(MESSAGE, reason=reason)


def _text(value: Any, reason: str) -> str:
    """文字列（None は空）。末尾の空白を除く（先頭・途中は保つ）。"""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise _fail(reason)
    return value.rstrip()


def normalize_action_plan(raw: str) -> str:
    """検証して、正規化した JSON 文字列を返す。規則に合わないときは InvalidInputError。"""
    try:
        obj = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise _fail("JSON として読めない") from exc
    if not isinstance(obj, dict) or not isinstance(obj.get("points"), list) or not obj["points"]:
        raise _fail("points がない")
    raw_legs = obj.get("legs", [])
    if not isinstance(raw_legs, list):
        raise _fail("legs が配列でない")
    if len(raw_legs) != len(obj["points"]) - 1:
        raise _fail("legs の件数が points - 1 でない")

    points: list[dict[str, str]] = []
    for index, item in enumerate(obj["points"]):
        if not isinstance(item, dict) or not set(item) <= _POINT_KEYS:
            raise _fail("地点の構造が違う")
        point = {key: _text(item.get(key), "地点の値が文字列でない") for key in _POINT_KEYS}
        if index == 0 and (point["arrive"] or point["depart"]):
            raise _fail("1 番目の地点に到着・出発がある")
        if point["time"] and (point["arrive"] or point["depart"]):
            raise _fail("time と arrive・depart が同時にある")
        points.append(point)

    legs: list[dict[str, str]] = []
    for item in raw_legs:
        if not isinstance(item, dict) or not set(item) <= _LEG_KEYS:
            raise _fail("経由メモの構造が違う")
        legs.append({key: _text(item.get(key), "経由メモの値が文字列でない") for key in _LEG_KEYS})

    # 2 番目以降で、すべて空の地点が末尾に続くときは取り除く（その地点への経由メモも）
    while len(points) > 1 and not any(points[-1].values()):
        points.pop()
        legs.pop()

    if not any(v for point in points for v in point.values()) and not any(
        v for leg in legs for v in leg.values()
    ):
        raise _fail("すべて空")

    out_points = [{"place": p["place"], **{k: p[k] for k in ("time", "arrive", "depart") if p[k]}} for p in points]
    out_legs = [{"memo": leg["memo"], "note": leg["note"]} for leg in legs]
    return json.dumps({"points": out_points, "legs": out_legs}, ensure_ascii=False)
