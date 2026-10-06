"""電灯の調光パターン（固定 4 種）。値はコードの定数とし、DB・`.env` に持たない（design.md）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DimmingPattern:
    id: str
    name: str
    brightness: int  # 1〜100
    color_temperature: int  # 2700〜6500

    def to_dict(self) -> dict[str, str | int]:
        return {
            "id": self.id,
            "name": self.name,
            "brightness": self.brightness,
            "color_temperature": self.color_temperature,
        }


# 並びは、画面の選択肢の並び（全灯、読書、くつろぎ、夜）
PATTERNS: tuple[DimmingPattern, ...] = (
    DimmingPattern("full", "全灯", 100, 6200),
    DimmingPattern("reading", "読書", 80, 5000),
    DimmingPattern("relax", "くつろぎ", 50, 3000),
    DimmingPattern("night", "夜", 10, 2700),
)

# 調光パターンを選ばずに電灯を ON にするときのパターン
DEFAULT_PATTERN_ID = "full"

_BY_ID = {p.id: p for p in PATTERNS}


def find(pattern_id: str) -> DimmingPattern | None:
    """識別子からパターンを引く。4 種のいずれでもなければ None。"""
    return _BY_ID.get(pattern_id)


def resolve(pattern_id: str | None) -> DimmingPattern | None:
    """省略（None）なら既定のパターン。4 種のいずれでもなければ None。"""
    return _BY_ID.get(DEFAULT_PATTERN_ID if pattern_id is None else pattern_id)


def turn_on_commands(pattern: DimmingPattern) -> tuple[tuple[str, str], ...]:
    """電灯を、パターンで点灯するための SwitchBot の指示（コマンド, 値）を、送る順に返す。"""
    return (
        ("turnOn", "default"),
        ("setBrightness", str(pattern.brightness)),
        ("setColorTemperature", str(pattern.color_temperature)),
    )
