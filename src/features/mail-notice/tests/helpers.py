from __future__ import annotations

from datetime import date, time
from uuid import uuid4

from app.db import get_conn


def unique(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


def insert_user(*, email: str = "user@example.com", is_deleted: bool = False) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.users (username, password_hash, email, is_deleted)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (unique("mn"), "x", email, is_deleted),
            )
            row = cur.fetchone()
            assert row is not None
            return int(row["id"])


def insert_category(user_id: int) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO schedule.categories (user_id, name, color)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (user_id, unique("cat"), "#4DA3FF"),
            )
            row = cur.fetchone()
            assert row is not None
            return int(row["id"])


def insert_schedule(
    user_id: int,
    category_id: int,
    *,
    title: str | None = None,
    kind: str = "event",
    granularity: str = "day",
    start_date: date,
    start_time: time | None = None,
    is_completed: bool | None = None,
    needs_notification: bool = True,
    is_deleted: bool = False,
) -> int:
    end_time = start_time
    completed = is_completed
    if kind == "todo" and completed is None:
        completed = False
    if kind == "event":
        completed = None
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO schedule.schedules (
                    user_id, category_id, title, kind, granularity,
                    start_date, end_date, start_time, end_time,
                    is_completed, needs_notification, is_deleted
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    user_id,
                    category_id,
                    title or unique("title"),
                    kind,
                    granularity,
                    start_date,
                    start_date,
                    start_time,
                    end_time,
                    completed,
                    needs_notification,
                    is_deleted,
                ),
            )
            row = cur.fetchone()
            assert row is not None
            return int(row["id"])


def notified_exists(schedule_id: int) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM mail_notice.notified_schedules
                WHERE schedule_id = %s
                """,
                (schedule_id,),
            )
            return cur.fetchone() is not None


def insert_notified_row(schedule_id: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mail_notice.notified_schedules (schedule_id)
                VALUES (%s)
                ON CONFLICT (schedule_id) DO NOTHING
                """,
                (schedule_id,),
            )


def cleanup(schedule_ids: list[int], category_ids: list[int], user_ids: list[int]) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            if schedule_ids:
                cur.execute(
                    """
                    DELETE FROM mail_notice.notified_schedules
                    WHERE schedule_id = ANY(%s)
                    """,
                    (schedule_ids,),
                )
                cur.execute(
                    "DELETE FROM schedule.schedules WHERE id = ANY(%s)",
                    (schedule_ids,),
                )
            if category_ids:
                cur.execute(
                    "DELETE FROM schedule.categories WHERE id = ANY(%s)",
                    (category_ids,),
                )
            if user_ids:
                cur.execute(
                    "DELETE FROM public.users WHERE id = ANY(%s)",
                    (user_ids,),
                )
