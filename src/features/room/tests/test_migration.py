"""既存の DB の移行（sql/02_room_actions.sql）のテスト（T-021）。

別の一時スキーマに、旧い定義（01）を作り、従来の行を入れてから、移行（02）を適用する。
本物の room スキーマには触れない。
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import psycopg2
import pytest
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2.extras import RealDictCursor

from app.config import load_config
from helpers import insert_user, unique

SQL_DIR = Path(__file__).resolve().parents[1] / "backend" / "sql"
OLD_DDL = (SQL_DIR / "01_room.sql").read_text(encoding="utf-8")
MIGRATION = (SQL_DIR / "02_room_actions.sql").read_text(encoding="utf-8")


def _connect(user: str | None = None, password: str | None = None):  # type: ignore[no-untyped-def]
    cfg = load_config()
    return psycopg2.connect(
        host=cfg.db_server,
        dbname=cfg.db_name,
        port=cfg.db_port,
        user=user or cfg.db_username,
        password=password if password is not None else cfg.db_password,
        cursor_factory=RealDictCursor,
    )


def _sql(text: str, schema: str) -> str:
    """DDL の room. を、一時スキーマの名前に置き換える。"""
    return text.replace("room.", f"{schema}.")


@pytest.fixture()
def schema() -> Iterator[str]:
    """一時スキーマを作り、終わりに削除する。DB に接続できないときは、テストを飛ばす。"""
    name = f"room_mig_{uuid4().hex[:8]}"
    cfg = load_config()
    try:
        admin = _connect("postgres", "postgres")
    except psycopg2.OperationalError as exc:
        pytest.skip(f"開発用 DB に接続できません: {exc}")
    admin.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    with admin.cursor() as cur:
        cur.execute(f'CREATE SCHEMA {name} AUTHORIZATION "{cfg.db_username}"')
    admin.close()
    yield name
    admin = _connect("postgres", "postgres")
    admin.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    with admin.cursor() as cur:
        cur.execute(f"DROP SCHEMA IF EXISTS {name} CASCADE")
    admin.close()


def run(schema: str, text: str) -> None:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(_sql(text, schema))
        conn.commit()
    finally:
        conn.close()


def query(schema: str, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(_sql(sql, schema), params)
            rows = [dict(r) for r in cur.fetchall()] if cur.description else []
        conn.commit()
        return rows
    finally:
        conn.close()


def execute(schema: str, sql: str, params: tuple[Any, ...] = ()) -> None:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(_sql(sql, schema), params)
        conn.commit()
    finally:
        conn.close()


def legacy_rows(schema: str, user_id: int) -> dict[str, int]:
    """旧い定義（01 だけ）に、従来の行を入れる。種類ごとの識別子を返す。"""
    run(schema, OLD_DDL)
    ids: dict[str, int] = {}
    for key, condition, scene, enabled in [
        ("daily", "daily", "out", True),
        ("weekdays", "weekdays", "indoor_speaker", True),
        ("holiday", "holiday", "ceiling_light", True),
    ]:
        row = query(
            schema,
            "INSERT INTO room.room_schedules (created_by_user_id, condition_type, run_time, scene, is_enabled) "
            "VALUES (%s, %s, '07:00', %s, %s) RETURNING id",
            (user_id, condition, scene, enabled),
        )
        ids[key] = int(row[0]["id"])
    execute(
        schema,
        "INSERT INTO room.schedule_weekdays (schedule_id, weekday) VALUES (%s, 1), (%s, 3)",
        (ids["weekdays"], ids["weekdays"]),
    )
    execute(
        schema,
        "UPDATE room.room_schedules SET last_run_at = '2026-10-01T07:00:02+09:00', "
        "last_run_result = 'partial', last_failed_devices = ARRAY['bedside_speaker'] WHERE id = %s",
        (ids["weekdays"],),
    )
    execute(
        schema,
        "INSERT INTO room.schedule_runs (schedule_id, run_date) VALUES (%s, '2026-10-01')",
        (ids["weekdays"],),
    )
    return ids


@pytest.fixture()
def user_id() -> int:
    return insert_user(unique("room_mig_user"))


def snapshot(schema: str) -> list[dict[str, Any]]:
    return query(schema, "SELECT * FROM room.room_schedules ORDER BY id")


# ---- ファイルの構成 ----


def test_適用の順は_01_02_03_04() -> None:
    sys.path.insert(0, str(SQL_DIR))
    import apply  # noqa: PLC0415

    assert [p.name for p in apply.DDL_PATHS] == [
        "01_room.sql",
        "02_room_actions.sql",
        "03_room_dimming.sql",
        "04_room_schedule_title_order.sql",
    ]


# ---- 旧い定義からの移行 ----


def test_既存の行は_一括切替_祝日は関係しない_当日になる(schema: str, user_id: int) -> None:
    ids = legacy_rows(schema, user_id)
    run(schema, MIGRATION)

    rows = {r["id"]: r for r in snapshot(schema)}
    for key in ("daily", "weekdays"):
        row = rows[ids[key]]
        assert (row["action_type"], row["holiday_mode"], row["day_shift"]) == ("scene", "none", "same")
        assert row["device"] is None and row["target_state"] is None
        assert row["is_enabled"] is True  # 有効のまま、従来どおり動く
    assert rows[ids["daily"]]["scene"] == "out"
    assert rows[ids["weekdays"]]["scene"] == "indoor_speaker"
    assert rows[ids["daily"]]["condition_type"] == "daily"
    assert rows[ids["weekdays"]]["condition_type"] == "weekdays"


def test_従来の祝日の指定は_無効の全曜日の曜日の指定に変換される(schema: str, user_id: int) -> None:
    ids = legacy_rows(schema, user_id)
    run(schema, MIGRATION)

    row = {r["id"]: r for r in snapshot(schema)}[ids["holiday"]]
    assert row["condition_type"] == "weekdays"
    assert row["is_enabled"] is False  # 無効にして残す（意味が変わるため）
    assert (row["holiday_mode"], row["day_shift"], row["action_type"]) == ("none", "same", "scene")
    assert row["scene"] == "ceiling_light"  # 実行内容は変えない
    weekdays = query(schema, "SELECT weekday FROM room.schedule_weekdays WHERE schedule_id = %s ORDER BY weekday", (ids["holiday"],))
    assert [w["weekday"] for w in weekdays] == [1, 2, 3, 4, 5, 6, 7]


def test_祝日の指定以外の行の_曜日_最終実行_実行記録は変わらない(schema: str, user_id: int) -> None:
    ids = legacy_rows(schema, user_id)
    run(schema, MIGRATION)

    row = {r["id"]: r for r in snapshot(schema)}[ids["weekdays"]]
    assert row["last_run_result"] == "partial"
    assert row["last_failed_devices"] == ["bedside_speaker"]
    assert row["last_run_at"] is not None
    weekdays = query(schema, "SELECT weekday FROM room.schedule_weekdays WHERE schedule_id = %s ORDER BY weekday", (ids["weekdays"],))
    assert [w["weekday"] for w in weekdays] == [1, 3]
    runs = query(schema, "SELECT run_date FROM room.schedule_runs WHERE schedule_id = %s", (ids["weekdays"],))
    assert len(runs) == 1


def test_繰り返し適用しても_壊れず_2回目で行が変わらない(schema: str, user_id: int) -> None:
    legacy_rows(schema, user_id)
    run(schema, MIGRATION)
    first = snapshot(schema)
    run(schema, MIGRATION)
    run(schema, MIGRATION)
    assert snapshot(schema) == first  # updated_at も変わらない（変換は 1 回目だけ効く）


def test_移行のあと_利用者が祝日の指定だった行を見直して有効にできる(schema: str, user_id: int) -> None:
    ids = legacy_rows(schema, user_id)
    run(schema, MIGRATION)
    execute(
        schema,
        "UPDATE room.room_schedules SET holiday_mode = 'include', is_enabled = true WHERE id = %s",
        (ids["holiday"],),
    )
    row = {r["id"]: r for r in snapshot(schema)}[ids["holiday"]]
    assert row["is_enabled"] is True and row["holiday_mode"] == "include"
    run(schema, MIGRATION)  # 再適用しても、見直した内容を壊さない
    row = {r["id"]: r for r in snapshot(schema)}[ids["holiday"]]
    assert row["is_enabled"] is True and row["holiday_mode"] == "include"


# ---- 空の DB（01 → 02） ----


def test_空のDBに_01_と_02_を順に適用しても同じ構造になる(schema: str) -> None:
    run(schema, OLD_DDL)
    run(schema, MIGRATION)
    columns = {
        r["column_name"]: r
        for r in query(
            schema.replace("room.", ""),
            "SELECT column_name, is_nullable, column_default FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = 'room_schedules'",
            (schema,),
        )
    }
    for name in ("holiday_mode", "day_shift", "action_type", "device", "target_state"):
        assert name in columns, name
    assert columns["scene"]["is_nullable"] == "YES"
    assert columns["holiday_mode"]["is_nullable"] == "NO" and "'none'" in columns["holiday_mode"]["column_default"]
    assert columns["day_shift"]["is_nullable"] == "NO" and "'same'" in columns["day_shift"]["column_default"]
    assert columns["action_type"]["is_nullable"] == "NO" and "'scene'" in columns["action_type"]["column_default"]
    assert columns["device"]["is_nullable"] == "YES" and columns["target_state"]["is_nullable"] == "YES"


# ---- 制約 ----

BASE = {"condition_type": "weekdays", "run_time": "07:00", "scene": "out"}


def insert(schema: str, user_id: int, **override: Any) -> int:
    values: dict[str, Any] = {"created_by_user_id": user_id, **BASE, **override}
    columns = ", ".join(values)
    placeholders = ", ".join(["%s"] * len(values))
    rows = query(
        schema,
        f"INSERT INTO room.room_schedules ({columns}) VALUES ({placeholders}) RETURNING id",
        tuple(values.values()),
    )
    return int(rows[0]["id"])


@pytest.fixture()
def migrated(schema: str) -> str:
    run(schema, OLD_DDL)
    run(schema, MIGRATION)
    return schema


@pytest.mark.parametrize(
    "override",
    [
        {"condition_type": "holiday"},  # 祝日の単独指定は無い
        {"holiday_mode": "all"},
        {"day_shift": "tomorrow"},
        {"condition_type": "daily", "holiday_mode": "include"},  # 毎日には、祝日の扱いを付けない
        {"condition_type": "daily", "holiday_mode": "exclude"},
        {"condition_type": "daily", "day_shift": "before"},
        {"condition_type": "daily", "day_shift": "after"},
        {"action_type": "other"},
        {"action_type": "scene", "scene": None},  # 一括切替なのに、scene が無い
        {"action_type": "scene", "device": "indirect_light", "target_state": "on"},  # 一括切替なのに、機器がある
        {"action_type": "scene", "device": "indirect_light"},
        {"action_type": "scene", "target_state": "on"},
        {"action_type": "device", "scene": "out", "device": "indirect_light", "target_state": "on"},  # 両方
        {"action_type": "device", "scene": None},  # 個別切替なのに、機器も状態も無い
        {"action_type": "device", "scene": None, "device": "indirect_light"},  # 状態が無い
        {"action_type": "device", "scene": None, "target_state": "on"},  # 機器が無い
        {"action_type": "device", "scene": None, "device": "front_door", "target_state": "on"},  # 玄関ドアは対象外
        {"action_type": "device", "scene": None, "device": "indirect_light", "target_state": "ON"},
        {"action_type": "device", "scene": None, "device": "indirect_light", "target_state": "xyz"},
        {"scene": "front_door"},
    ],
)
def test_不正な組み合わせは_制約が拒否する(migrated: str, user_id: int, override: dict[str, Any]) -> None:
    with pytest.raises(psycopg2.errors.CheckViolation):
        insert(migrated, user_id, **override)


@pytest.mark.parametrize("device", ["ceiling_light", "indirect_light", "indoor_speaker", "bedside_speaker"])
@pytest.mark.parametrize("state", ["on", "off"])
def test_機器の個別切替は_4機器とON_OFFで登録できる(migrated: str, user_id: int, device: str, state: str) -> None:
    schedule_id = insert(migrated, user_id, action_type="device", scene=None, device=device, target_state=state)
    row = query(migrated, "SELECT * FROM room.room_schedules WHERE id = %s", (schedule_id,))[0]
    assert (row["action_type"], row["scene"], row["device"], row["target_state"]) == ("device", None, device, state)


@pytest.mark.parametrize("mode", ["none", "include", "exclude"])
@pytest.mark.parametrize("shift", ["same", "before", "after"])
def test_曜日の指定は_祝日の扱いと実行日の取り方の9通りを登録できる(migrated: str, user_id: int, mode: str, shift: str) -> None:
    schedule_id = insert(migrated, user_id, holiday_mode=mode, day_shift=shift)
    row = query(migrated, "SELECT holiday_mode, day_shift FROM room.room_schedules WHERE id = %s", (schedule_id,))[0]
    assert (row["holiday_mode"], row["day_shift"]) == (mode, shift)


def test_毎日は_既定の祝日の扱いと実行日の取り方なら登録できる(migrated: str, user_id: int) -> None:
    schedule_id = insert(migrated, user_id, condition_type="daily")
    row = query(migrated, "SELECT holiday_mode, day_shift FROM room.room_schedules WHERE id = %s", (schedule_id,))[0]
    assert (row["holiday_mode"], row["day_shift"]) == ("none", "same")


def test_定期実行を削除すると曜日と実行記録も消える(migrated: str, user_id: int) -> None:
    schedule_id = insert(migrated, user_id, action_type="device", scene=None, device="indoor_speaker", target_state="off")
    execute(migrated, "INSERT INTO room.schedule_weekdays VALUES (%s, 2)", (schedule_id,))
    execute(migrated, "INSERT INTO room.schedule_runs (schedule_id, run_date) VALUES (%s, '2026-10-01')", (schedule_id,))
    execute(migrated, "DELETE FROM room.room_schedules WHERE id = %s", (schedule_id,))
    assert query(migrated, "SELECT 1 FROM room.schedule_weekdays WHERE schedule_id = %s", (schedule_id,)) == []
    assert query(migrated, "SELECT 1 FROM room.schedule_runs WHERE schedule_id = %s", (schedule_id,)) == []
