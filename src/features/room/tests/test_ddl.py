from __future__ import annotations

import sys
from collections.abc import Iterator
from uuid import uuid4

import psycopg2
import pytest

from app.db import get_conn

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "backend" / "sql"))
import apply  # noqa: E402  (backend/sql/apply.py)


@pytest.fixture(scope="module", autouse=True)
def applied_schema() -> None:
    """スキーマと DDL を適用する。DB に接続できないときはテストを飛ばす。"""
    try:
        apply.create_schema("postgres", "postgres")
        apply.apply_ddl()
    except psycopg2.OperationalError as exc:
        pytest.skip(f"開発用 DB に接続できません: {exc}")


@pytest.fixture
def user_id() -> Iterator[int]:
    """テスト用ユーザを作り、終了時に定期実行を消してからユーザも消す。"""
    name = f"room_ddl_{uuid4().hex[:8]}"
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO public.users (username, password_hash) VALUES (%s, %s) RETURNING id",
            (name, "x"),
        )
        row = cur.fetchone()
        assert row is not None
        uid = int(row["id"])
    yield uid
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM room.room_schedules WHERE created_by_user_id = %s", (uid,))
        cur.execute("DELETE FROM public.users WHERE id = %s", (uid,))


def _insert_schedule(user_id: int, **override: object) -> int:
    values: dict[str, object] = {
        "condition_type": "daily",
        "run_time": "07:00",
        "scene": "out",
    }
    values.update(override)
    columns = ["created_by_user_id", *values.keys()]
    placeholders = ", ".join(["%s"] * len(columns))
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO room.room_schedules ({', '.join(columns)}) "
            f"VALUES ({placeholders}) RETURNING id",
            [user_id, *values.values()],
        )
        row = cur.fetchone()
        assert row is not None
        return int(row["id"])


def test_DDLを繰り返し適用しても壊れない() -> None:
    apply.apply_ddl()
    apply.apply_ddl()


def test_既定値で登録できる(user_id: int) -> None:
    schedule_id = _insert_schedule(user_id)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM room.room_schedules WHERE id = %s", (schedule_id,))
        row = cur.fetchone()
    assert row is not None
    assert row["is_enabled"] is True
    assert row["last_run_at"] is None
    assert row["last_run_result"] is None
    assert row["last_failed_devices"] == []


@pytest.mark.parametrize(
    "override",
    [
        {"condition_type": "monthly"},
        {"scene": "front_door"},
        {"run_time": "07:00:30"},
        {"last_run_result": "failure"},  # 日時なしで結果だけは不可
        {"last_run_result": "success", "last_run_at": "2026-10-01T07:00:00+09:00"},
    ],
    ids=["実行条件不正", "一括切替不正", "秒つき時刻", "日時なしの結果", "（正常）結果と日時の組"],
)
def test_CHECK制約(user_id: int, override: dict[str, object]) -> None:
    if override.get("last_run_result") == "success" and "last_run_at" in override:
        # 結果と日時が揃っていれば登録できる
        _insert_schedule(user_id, **override)
        return
    with pytest.raises(psycopg2.errors.CheckViolation):
        _insert_schedule(user_id, **override)


def test_失敗した機器は4機器の名称だけ許す(user_id: int) -> None:
    _insert_schedule(
        user_id,
        last_run_at="2026-10-01T07:00:00+09:00",
        last_run_result="partial",
        last_failed_devices=["indirect_light", "bedside_speaker"],
    )
    with pytest.raises(psycopg2.errors.CheckViolation):
        _insert_schedule(
            user_id,
            last_run_at="2026-10-01T07:00:00+09:00",
            last_run_result="partial",
            last_failed_devices=["front_door"],
        )


def test_存在しないユーザでは登録できない() -> None:
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        _insert_schedule(-1)


def test_曜日は1から7だけで同じ曜日は重ねられない(user_id: int) -> None:
    schedule_id = _insert_schedule(user_id, condition_type="weekdays")
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO room.schedule_weekdays (schedule_id, weekday) VALUES (%s, 1), (%s, 7)",
            (schedule_id, schedule_id),
        )
    with pytest.raises(psycopg2.errors.CheckViolation):
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO room.schedule_weekdays (schedule_id, weekday) VALUES (%s, 0)",
                (schedule_id,),
            )
    with pytest.raises(psycopg2.errors.CheckViolation):
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO room.schedule_weekdays (schedule_id, weekday) VALUES (%s, 8)",
                (schedule_id,),
            )
    with pytest.raises(psycopg2.errors.UniqueViolation):
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO room.schedule_weekdays (schedule_id, weekday) VALUES (%s, 1)",
                (schedule_id,),
            )


def test_同じ日の実行記録は1件だけ追加できる(user_id: int) -> None:
    schedule_id = _insert_schedule(user_id)
    sql = (
        "INSERT INTO room.schedule_runs (schedule_id, run_date) VALUES (%s, %s) "
        "ON CONFLICT DO NOTHING"
    )
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (schedule_id, "2026-10-01"))
        assert cur.rowcount == 1
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (schedule_id, "2026-10-01"))
        assert cur.rowcount == 0  # 2 回目は追加されない（重複実行の防止）
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (schedule_id, "2026-10-02"))
        assert cur.rowcount == 1  # 別の日は追加できる


def test_定期実行を削除すると曜日と実行記録も消える(user_id: int) -> None:
    schedule_id = _insert_schedule(user_id, condition_type="weekdays")
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO room.schedule_weekdays (schedule_id, weekday) VALUES (%s, 3)",
            (schedule_id,),
        )
        cur.execute(
            "INSERT INTO room.schedule_runs (schedule_id, run_date) VALUES (%s, %s)",
            (schedule_id, "2026-10-01"),
        )
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM room.room_schedules WHERE id = %s", (schedule_id,))
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM room.schedule_weekdays WHERE schedule_id = %s", (schedule_id,))
        assert cur.fetchone()["n"] == 0
        cur.execute("SELECT count(*) AS n FROM room.schedule_runs WHERE schedule_id = %s", (schedule_id,))
        assert cur.fetchone()["n"] == 0
