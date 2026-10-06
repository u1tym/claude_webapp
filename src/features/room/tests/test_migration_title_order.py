"""定期実行のタイトルと表示順の移行（sql/04_room_schedule_title_order.sql）のテスト（T-037）。

別の一時スキーマに、01 → 02 → 03 を適用し、従来の行を入れてから、04 を適用する。
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
TITLE_ORDER = (SQL_DIR / "04_room_schedule_title_order.sql").read_text(encoding="utf-8")


@pytest.fixture()
def migrated(schema: str) -> str:  # noqa: F811
    """01 → 02 → 03 → 04 を適用した、空の DB。"""
    for text in (OLD_DDL, MIGRATION, DIMMING, TITLE_ORDER):
        run(schema, text)
    return schema


# ---- 旧い定義からの移行 ----


def test_既存の行は変わらず_タイトルと表示順はNULLになる(schema: str, user_id: int) -> None:  # noqa: F811
    legacy_rows(schema, user_id)
    run(schema, MIGRATION)
    run(schema, DIMMING)
    before = {r["id"]: r for r in snapshot(schema)}

    run(schema, TITLE_ORDER)

    after = {r["id"]: r for r in snapshot(schema)}
    assert set(after) == set(before) and before
    for schedule_id, row in after.items():
        assert row["title"] is None and row["display_order"] is None
        assert {k: v for k, v in row.items() if k not in ("title", "display_order")} == before[schedule_id]


def test_最終実行_曜日_実行記録は変わらない(schema: str, user_id: int) -> None:  # noqa: F811
    ids = legacy_rows(schema, user_id)
    run(schema, MIGRATION)
    run(schema, DIMMING)
    run(schema, TITLE_ORDER)

    row = {r["id"]: r for r in snapshot(schema)}[ids["weekdays"]]
    assert row["last_run_result"] == "partial"
    assert row["last_failed_devices"] == ["bedside_speaker"]
    weekdays = query(
        schema, "SELECT weekday FROM room.schedule_weekdays WHERE schedule_id = %s ORDER BY weekday", (ids["weekdays"],)
    )
    assert [w["weekday"] for w in weekdays] == [1, 3]
    assert len(query(schema, "SELECT 1 FROM room.schedule_runs WHERE schedule_id = %s", (ids["weekdays"],))) == 1


def test_繰り返し適用しても_壊れず_付けた値も行も変わらない(schema: str, user_id: int) -> None:  # noqa: F811
    legacy_rows(schema, user_id)
    for text in (MIGRATION, DIMMING, TITLE_ORDER):
        run(schema, text)
    insert(schema, user_id, title="朝の読書灯", display_order=3)
    first = snapshot(schema)
    run(schema, TITLE_ORDER)
    run(schema, TITLE_ORDER)
    assert snapshot(schema) == first  # 付けたタイトル・表示順も、updated_at も変わらない


# ---- 空の DB（01 → 02 → 03 → 04） ----


def test_空のDBに順に適用すると_列とインデックスがある(migrated: str) -> None:
    columns = {
        r["column_name"]: r
        for r in query(
            migrated,
            "SELECT column_name, is_nullable, column_default, data_type, character_maximum_length "
            "FROM information_schema.columns WHERE table_schema = %s AND table_name = 'room_schedules'",
            (migrated,),
        )
    }
    title = columns["title"]
    assert title["is_nullable"] == "YES" and title["column_default"] is None
    assert title["data_type"] == "character varying" and title["character_maximum_length"] == 50
    order = columns["display_order"]
    assert order["is_nullable"] == "YES" and order["column_default"] is None
    assert order["data_type"] == "integer"

    indexes = {
        r["indexname"]: r["indexdef"]
        for r in query(
            migrated,
            "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = %s AND tablename = 'room_schedules'",
            (migrated,),
        )
    }
    assert "ix_room_schedules_display_order" in indexes
    assert "(display_order, run_time, id)" in indexes["ix_room_schedules_display_order"]


# ---- 制約 ----


@pytest.mark.parametrize(
    "title",
    ["a", "朝", "朝の読書灯", "朝 の読書灯", "x" * 50, "あ" * 50],
)
def test_1から50文字の_前後に空白のないタイトルは登録できる(migrated: str, user_id: int, title: str) -> None:  # noqa: F811
    schedule_id = insert(migrated, user_id, title=title)
    row = query(migrated, "SELECT title FROM room.room_schedules WHERE id = %s", (schedule_id,))[0]
    assert row["title"] == title


@pytest.mark.parametrize("title", ["", " ", "  ", " a", "a ", " a ", "a  "])
def test_空_前後に空白があるタイトルは_制約が拒否する(migrated: str, user_id: int, title: str) -> None:  # noqa: F811
    with pytest.raises(psycopg2.errors.CheckViolation):
        insert(migrated, user_id, title=title)


@pytest.mark.parametrize("title", ["x" * 51, "あ" * 51, "x" * 200])
def test_51文字以上のタイトルは_列の長さで拒否される(migrated: str, user_id: int, title: str) -> None:  # noqa: F811
    # varchar(50) が、先に拒否する（CHECK の 50 文字の上限は、列の長さと重ねた二重の守り）
    with pytest.raises(psycopg2.errors.StringDataRightTruncation):
        insert(migrated, user_id, title=title)


@pytest.mark.parametrize("order", [0, 1, 100, 9999])
def test_0から9999の表示順は登録できる(migrated: str, user_id: int, order: int) -> None:  # noqa: F811
    schedule_id = insert(migrated, user_id, display_order=order)
    row = query(migrated, "SELECT display_order FROM room.room_schedules WHERE id = %s", (schedule_id,))[0]
    assert row["display_order"] == order


@pytest.mark.parametrize("order", [-1, 10000, 100000])
def test_範囲外の表示順は_制約が拒否する(migrated: str, user_id: int, order: int) -> None:  # noqa: F811
    with pytest.raises(psycopg2.errors.CheckViolation):
        insert(migrated, user_id, display_order=order)


def test_タイトルも表示順も無い行は登録できる(migrated: str, user_id: int) -> None:  # noqa: F811
    schedule_id = insert(migrated, user_id)
    row = query(migrated, "SELECT title, display_order FROM room.room_schedules WHERE id = %s", (schedule_id,))[0]
    assert (row["title"], row["display_order"]) == (None, None)


def test_更新で外す_付け替える(migrated: str, user_id: int) -> None:  # noqa: F811
    schedule_id = insert(migrated, user_id, title="朝", display_order=2)
    execute(migrated, "UPDATE room.room_schedules SET title = NULL, display_order = NULL WHERE id = %s", (schedule_id,))
    row = query(migrated, "SELECT title, display_order FROM room.room_schedules WHERE id = %s", (schedule_id,))[0]
    assert (row["title"], row["display_order"]) == (None, None)
    with pytest.raises(psycopg2.errors.CheckViolation):
        execute(migrated, "UPDATE room.room_schedules SET title = '' WHERE id = %s", (schedule_id,))


# ---- 並び ----


def test_並びは_表示順の昇順で_表示順なしが末尾_同じ値の中は時刻とidの順(migrated: str, user_id: int) -> None:  # noqa: F811
    ids = {
        "order2_late": insert(migrated, user_id, display_order=2, run_time="09:00"),
        "none_early": insert(migrated, user_id, run_time="06:00"),
        "order1": insert(migrated, user_id, display_order=1, run_time="23:00"),
        "order2_early": insert(migrated, user_id, display_order=2, run_time="08:00"),
        "order0": insert(migrated, user_id, display_order=0, run_time="23:59"),
        "none_late": insert(migrated, user_id, run_time="22:00"),
    }
    rows = query(
        migrated,
        "SELECT id FROM room.room_schedules WHERE created_by_user_id = %s "
        "ORDER BY display_order ASC NULLS LAST, run_time, id",
        (user_id,),
    )
    assert [r["id"] for r in rows] == [
        ids["order0"],
        ids["order1"],
        ids["order2_early"],
        ids["order2_late"],
        ids["none_early"],
        ids["none_late"],
    ]


def test_PostgreSQLの昇順は_NULLを末尾に置く(migrated: str, user_id: int) -> None:  # noqa: F811
    """NULLS LAST を書かなくても末尾になること（インデックスの並びと、ORDER BY の既定が合う前提）。"""
    insert(migrated, user_id, run_time="01:00")
    insert(migrated, user_id, display_order=5, run_time="02:00")
    rows: list[dict[str, Any]] = query(
        migrated,
        "SELECT display_order FROM room.room_schedules WHERE created_by_user_id = %s ORDER BY display_order ASC",
        (user_id,),
    )
    assert [r["display_order"] for r in rows] == [5, None]
