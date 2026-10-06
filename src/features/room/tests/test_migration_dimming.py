"""電灯の調光の移行（sql/03_room_dimming.sql）のテスト（T-029）。

別の一時スキーマに、01 → 02 を適用し、従来の行を入れてから、03 を適用する。
本物の room スキーマには触れない。一時スキーマの作り方は、test_migration.py と同じ。
"""

from __future__ import annotations

from typing import Any

import psycopg2
import pytest

from test_migration import (  # noqa: F401  フィクスチャとして使う
    MIGRATION,
    OLD_DDL,
    SQL_DIR,
    execute,
    insert,
    legacy_rows,
    query,
    run,
    schema,
    snapshot,
    user_id,
)

DIMMING = (SQL_DIR / "03_room_dimming.sql").read_text(encoding="utf-8")

CEILING_ON = {"action_type": "device", "scene": None, "device": "ceiling_light", "target_state": "on"}


@pytest.fixture()
def migrated(schema: str) -> str:  # noqa: F811
    """01 → 02 → 03 を適用した、空の DB。"""
    run(schema, OLD_DDL)
    run(schema, MIGRATION)
    run(schema, DIMMING)
    return schema


# ---- 旧い定義からの移行 ----


def test_既存の行は_変わらず_調光パターンはNULLになる(schema: str, user_id: int) -> None:  # noqa: F811
    ids = legacy_rows(schema, user_id)
    run(schema, MIGRATION)
    # 電灯の個別切替も、移行前から存在していたものとして入れる
    ceiling_id = insert(schema, user_id, **CEILING_ON)
    before = {r["id"]: r for r in snapshot(schema)}

    run(schema, DIMMING)

    after = {r["id"]: r for r in snapshot(schema)}
    assert set(after) == set(before)
    for schedule_id, row in after.items():
        assert row["dimming_pattern"] is None  # NULL = 既定のパターン（全灯）
        original = {k: v for k, v in before[schedule_id].items()}
        assert {k: v for k, v in row.items() if k != "dimming_pattern"} == original
    assert ceiling_id in after and ids["daily"] in after


def test_最終実行_曜日_実行記録は変わらない(schema: str, user_id: int) -> None:  # noqa: F811
    ids = legacy_rows(schema, user_id)
    run(schema, MIGRATION)
    run(schema, DIMMING)

    row = {r["id"]: r for r in snapshot(schema)}[ids["weekdays"]]
    assert row["last_run_result"] == "partial"
    assert row["last_failed_devices"] == ["bedside_speaker"]
    weekdays = query(
        schema, "SELECT weekday FROM room.schedule_weekdays WHERE schedule_id = %s ORDER BY weekday", (ids["weekdays"],)
    )
    assert [w["weekday"] for w in weekdays] == [1, 3]
    runs = query(schema, "SELECT run_date FROM room.schedule_runs WHERE schedule_id = %s", (ids["weekdays"],))
    assert len(runs) == 1


def test_繰り返し適用しても_壊れず_行が変わらない(schema: str, user_id: int) -> None:  # noqa: F811
    legacy_rows(schema, user_id)
    run(schema, MIGRATION)
    run(schema, DIMMING)
    insert(schema, user_id, dimming_pattern="reading", **CEILING_ON)
    first = snapshot(schema)
    run(schema, DIMMING)
    run(schema, DIMMING)
    assert snapshot(schema) == first  # 登録済みの調光パターンも、updated_at も変わらない


# ---- 空の DB（01 → 02 → 03） ----


def test_空のDBに_01_02_03_を順に適用すると_列がある(migrated: str) -> None:
    columns = {
        r["column_name"]: r
        for r in query(
            migrated,
            "SELECT column_name, is_nullable, column_default, data_type, character_maximum_length "
            "FROM information_schema.columns WHERE table_schema = %s AND table_name = 'room_schedules'",
            (migrated,),
        )
    }
    column = columns["dimming_pattern"]
    assert column["is_nullable"] == "YES"
    assert column["column_default"] is None
    assert column["data_type"] == "character varying" and column["character_maximum_length"] == 16


# ---- 制約 ----


@pytest.mark.parametrize("pattern", ["full", "reading", "relax", "night"])
def test_電灯をONにする個別切替は_4種の調光パターンで登録できる(migrated: str, user_id: int, pattern: str) -> None:  # noqa: F811
    schedule_id = insert(migrated, user_id, dimming_pattern=pattern, **CEILING_ON)
    row = query(migrated, "SELECT dimming_pattern FROM room.room_schedules WHERE id = %s", (schedule_id,))[0]
    assert row["dimming_pattern"] == pattern


def test_調光パターンを持たない電灯のONは_NULLで登録できる(migrated: str, user_id: int) -> None:  # noqa: F811
    schedule_id = insert(migrated, user_id, **CEILING_ON)
    row = query(migrated, "SELECT dimming_pattern FROM room.room_schedules WHERE id = %s", (schedule_id,))[0]
    assert row["dimming_pattern"] is None


@pytest.mark.parametrize(
    "override",
    [
        # 4 種以外の値
        {**CEILING_ON, "dimming_pattern": "dark"},
        {**CEILING_ON, "dimming_pattern": "FULL"},
        {**CEILING_ON, "dimming_pattern": ""},
        # 電灯を ON にする個別切替以外
        {"dimming_pattern": "full"},  # 一括切替（scene）
        {"scene": "ceiling_light", "dimming_pattern": "reading"},  # 電灯選択
        {"action_type": "device", "scene": None, "device": "ceiling_light", "target_state": "off", "dimming_pattern": "full"},
        {"action_type": "device", "scene": None, "device": "indirect_light", "target_state": "on", "dimming_pattern": "full"},
        {"action_type": "device", "scene": None, "device": "indoor_speaker", "target_state": "on", "dimming_pattern": "night"},
        {"action_type": "device", "scene": None, "device": "bedside_speaker", "target_state": "on", "dimming_pattern": "night"},
    ],
)
def test_不正な調光パターンは_制約が拒否する(migrated: str, user_id: int, override: dict[str, Any]) -> None:  # noqa: F811
    with pytest.raises(psycopg2.errors.CheckViolation):
        insert(migrated, user_id, **override)


def test_調光パターンを持つ行の更新で_電灯のOFFや他の機器へ変えると拒否される(migrated: str, user_id: int) -> None:  # noqa: F811
    schedule_id = insert(migrated, user_id, dimming_pattern="night", **CEILING_ON)
    with pytest.raises(psycopg2.errors.CheckViolation):
        execute(migrated, "UPDATE room.room_schedules SET target_state = 'off' WHERE id = %s", (schedule_id,))
    with pytest.raises(psycopg2.errors.CheckViolation):
        execute(migrated, "UPDATE room.room_schedules SET device = 'indirect_light' WHERE id = %s", (schedule_id,))
    # 調光パターンを外せば、OFF にできる
    execute(
        migrated,
        "UPDATE room.room_schedules SET dimming_pattern = NULL, target_state = 'off' WHERE id = %s",
        (schedule_id,),
    )
    row = query(migrated, "SELECT dimming_pattern, target_state FROM room.room_schedules WHERE id = %s", (schedule_id,))[0]
    assert (row["dimming_pattern"], row["target_state"]) == (None, "off")
