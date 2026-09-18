from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time

from app.db import get_conn


@dataclass(frozen=True)
class CandidateRow:
    id: int
    user_id: int
    title: str
    kind: str
    granularity: str
    start_date: date
    start_time: time | None
    is_completed: bool | None
    email: str
    user_deleted: bool


def _to_candidate(row: dict[str, object]) -> CandidateRow:
    start_time = row["start_time"]
    completed = row["is_completed"]
    return CandidateRow(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        title=str(row["title"]),
        kind=str(row["kind"]),
        granularity=str(row["granularity"]),
        start_date=row["start_date"],  # type: ignore[arg-type]
        start_time=start_time if start_time is not None else None,  # type: ignore[arg-type]
        is_completed=bool(completed) if completed is not None else None,
        email=str(row["email"] or ""),
        user_deleted=bool(row["user_deleted"]),
    )


def list_candidates(lower_date: date) -> list[CandidateRow]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.id, s.user_id, s.title, s.kind, s.granularity,
                       s.start_date, s.start_time, s.is_completed,
                       u.email, u.is_deleted AS user_deleted
                FROM schedule.schedules s
                INNER JOIN public.users u ON u.id = s.user_id
                WHERE s.is_deleted = false
                  AND s.needs_notification = true
                  AND s.start_date > %s
                ORDER BY s.id
                """,
                (lower_date,),
            )
            rows = cur.fetchall()
    return [_to_candidate(dict(row)) for row in rows]


def is_notified(schedule_id: int) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM mail_notice.notified_schedules
                WHERE schedule_id = %s
                """,
                (schedule_id,),
            )
            return cur.fetchone() is not None


def insert_notified(schedule_id: int) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mail_notice.notified_schedules (schedule_id)
                VALUES (%s)
                ON CONFLICT (schedule_id) DO NOTHING
                RETURNING schedule_id
                """,
                (schedule_id,),
            )
            return cur.fetchone() is not None
