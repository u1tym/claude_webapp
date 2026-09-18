from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from uuid import UUID

from app.db import get_conn


@dataclass(frozen=True)
class UserRow:
    id: int
    username: str
    is_deleted: bool


@dataclass(frozen=True)
class SessionRow:
    id: UUID
    user_id: int
    expires_at: datetime


@dataclass(frozen=True)
class SettingRow:
    key: str
    value_text: str | None
    value_bytes: bytes | None
    value_media_type: str | None


@dataclass(frozen=True)
class FeatureRow:
    id: str
    title: str
    url: str
    icon: bytes
    icon_media_type: str
    is_deleted: bool


@dataclass(frozen=True)
class CategoryRow:
    id: int
    user_id: int
    name: str
    color: str
    is_deleted: bool


@dataclass(frozen=True)
class ScheduleRow:
    id: int
    user_id: int
    category_id: int
    title: str
    location: str | None
    detail: str | None
    kind: str
    granularity: str
    start_date: date
    end_date: date
    start_time: time | None
    end_time: time | None
    is_completed: bool | None
    is_deleted: bool
    routine_id: int | None
    needs_notification: bool


@dataclass(frozen=True)
class PreferenceRow:
    user_id: int
    week_starts_on: str
    show_deleted: bool


@dataclass(frozen=True)
class UserHolidayRow:
    id: int
    user_id: int
    holiday_date: date
    name: str
    is_deleted: bool


@dataclass(frozen=True)
class RoutineRow:
    id: int
    user_id: int
    category_id: int
    title: str
    detail: str | None
    kind: str
    occurrence_type: str
    date_rule: str | None
    day_of_month: int | None
    weekday_rule: str | None
    weekday_n: int | None
    weekday: str | None
    adjust_excluded: bool
    shift_direction: str | None
    needs_notification: bool
    is_deleted: bool
    months: tuple[int, ...]
    exclusions: tuple[str, ...]


def get_user_by_username(username: str) -> UserRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, username, is_deleted
                FROM public.users
                WHERE username = %s
                """,
                (username,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return UserRow(
                id=int(row["id"]),
                username=str(row["username"]),
                is_deleted=bool(row["is_deleted"]),
            )


def get_user_by_id(user_id: int) -> UserRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, username, is_deleted
                FROM public.users
                WHERE id = %s
                """,
                (user_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return UserRow(
                id=int(row["id"]),
                username=str(row["username"]),
                is_deleted=bool(row["is_deleted"]),
            )


def get_session(session_id: UUID) -> SessionRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, expires_at
                FROM public.sessions
                WHERE id = %s
                """,
                (str(session_id),),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return SessionRow(
                id=UUID(str(row["id"])),
                user_id=int(row["user_id"]),
                expires_at=row["expires_at"],
            )


def update_session_expiry(session_id: UUID, expires_at: datetime) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.sessions
                SET expires_at = %s
                WHERE id = %s
                """,
                (expires_at, str(session_id)),
            )


def get_setting(key: str) -> SettingRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT key, value_text, value_bytes, value_media_type
                FROM public.system_settings
                WHERE key = %s
                """,
                (key,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            raw_bytes = row["value_bytes"]
            return SettingRow(
                key=str(row["key"]),
                value_text=str(row["value_text"]) if row["value_text"] is not None else None,
                value_bytes=bytes(raw_bytes) if raw_bytes is not None else None,
                value_media_type=(
                    str(row["value_media_type"]) if row["value_media_type"] is not None else None
                ),
            )


def get_feature(feature_id: str) -> FeatureRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, url, icon, icon_media_type, is_deleted
                FROM public.features
                WHERE id = %s
                """,
                (feature_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return FeatureRow(
                id=str(row["id"]),
                title=str(row["title"]),
                url=str(row["url"]),
                icon=bytes(row["icon"]),
                icon_media_type=str(row["icon_media_type"]),
                is_deleted=bool(row["is_deleted"]),
            )


def assignment_exists(user_id: int, feature_id: str) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM public.menu_assignments
                WHERE user_id = %s AND feature_id = %s
                """,
                (user_id, feature_id),
            )
            return cur.fetchone() is not None


def _category_from_row(row: dict[str, object]) -> CategoryRow:
    return CategoryRow(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        name=str(row["name"]),
        color=str(row["color"]),
        is_deleted=bool(row["is_deleted"]),
    )


def list_categories(user_id: int, include_deleted: bool) -> list[CategoryRow]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            if include_deleted:
                cur.execute(
                    """
                    SELECT id, user_id, name, color, is_deleted
                    FROM schedule.categories
                    WHERE user_id = %s
                    ORDER BY name ASC
                    """,
                    (user_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT id, user_id, name, color, is_deleted
                    FROM schedule.categories
                    WHERE user_id = %s AND is_deleted = false
                    ORDER BY name ASC
                    """,
                    (user_id,),
                )
            return [_category_from_row(row) for row in cur.fetchall()]


def get_category(user_id: int, category_id: int) -> CategoryRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, name, color, is_deleted
                FROM schedule.categories
                WHERE id = %s AND user_id = %s
                """,
                (category_id, user_id),
            )
            row = cur.fetchone()
            return _category_from_row(row) if row else None


def insert_category(user_id: int, name: str, color: str) -> CategoryRow:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO schedule.categories (user_id, name, color)
                VALUES (%s, %s, %s)
                RETURNING id, user_id, name, color, is_deleted
                """,
                (user_id, name, color),
            )
            row = cur.fetchone()
            assert row is not None
            return _category_from_row(row)


def update_category(category_id: int, user_id: int, name: str, color: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE schedule.categories
                SET name = %s, color = %s
                WHERE id = %s AND user_id = %s AND is_deleted = false
                """,
                (name, color, category_id, user_id),
            )


def logical_delete_category(category_id: int, user_id: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE schedule.categories
                SET is_deleted = true
                WHERE id = %s AND user_id = %s AND is_deleted = false
                """,
                (category_id, user_id),
            )


def _schedule_from_row(row: dict[str, object]) -> ScheduleRow:
    location = row["location"]
    detail = row["detail"]
    start_time = row["start_time"]
    end_time = row["end_time"]
    is_completed = row["is_completed"]
    return ScheduleRow(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        category_id=int(row["category_id"]),
        title=str(row["title"]),
        location=str(location) if location is not None else None,
        detail=str(detail) if detail is not None else None,
        kind=str(row["kind"]),
        granularity=str(row["granularity"]),
        start_date=row["start_date"],
        end_date=row["end_date"],
        start_time=start_time,
        end_time=end_time,
        is_completed=bool(is_completed) if is_completed is not None else None,
        is_deleted=bool(row["is_deleted"]),
        routine_id=int(row["routine_id"]) if row["routine_id"] is not None else None,
        needs_notification=bool(row["needs_notification"]),
    )


_SCHEDULE_SELECT = """
    SELECT id, user_id, category_id, title, location, detail, kind, granularity,
           start_date, end_date, start_time, end_time, is_completed, is_deleted, routine_id,
           needs_notification
    FROM schedule.schedules
"""

_SCHEDULE_ORDER = """
    ORDER BY
        CASE granularity WHEN 'day' THEN 0 ELSE 1 END,
        start_date ASC,
        start_time ASC NULLS FIRST,
        end_date ASC,
        end_time ASC NULLS FIRST,
        title ASC
"""


def list_schedules_overlapping(
    user_id: int,
    start_date: date,
    end_date: date,
) -> list[ScheduleRow]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                _SCHEDULE_SELECT
                + """
                WHERE user_id = %s
                  AND is_deleted = false
                  AND start_date <= %s
                  AND end_date >= %s
                """
                + _SCHEDULE_ORDER,
                (user_id, end_date, start_date),
            )
            return [_schedule_from_row(row) for row in cur.fetchall()]


def get_schedule(user_id: int, schedule_id: int) -> ScheduleRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                _SCHEDULE_SELECT + " WHERE id = %s AND user_id = %s",
                (schedule_id, user_id),
            )
            row = cur.fetchone()
            return _schedule_from_row(row) if row else None


def insert_schedule(
    user_id: int,
    category_id: int,
    title: str,
    location: str | None,
    detail: str | None,
    kind: str,
    granularity: str,
    start_date: date,
    end_date: date,
    start_time: time | None,
    end_time: time | None,
    is_completed: bool | None,
    needs_notification: bool,
    routine_id: int | None = None,
) -> ScheduleRow:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO schedule.schedules (
                    user_id, category_id, title, location, detail, kind, granularity,
                    start_date, end_date, start_time, end_time, is_completed, routine_id,
                    needs_notification
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, user_id, category_id, title, location, detail, kind, granularity,
                          start_date, end_date, start_time, end_time, is_completed, is_deleted,
                          routine_id, needs_notification
                """,
                (
                    user_id,
                    category_id,
                    title,
                    location,
                    detail,
                    kind,
                    granularity,
                    start_date,
                    end_date,
                    start_time,
                    end_time,
                    is_completed,
                    routine_id,
                    needs_notification,
                ),
            )
            row = cur.fetchone()
            assert row is not None
            return _schedule_from_row(row)


def update_schedule(
    schedule_id: int,
    user_id: int,
    category_id: int,
    title: str,
    location: str | None,
    detail: str | None,
    kind: str,
    granularity: str,
    start_date: date,
    end_date: date,
    start_time: time | None,
    end_time: time | None,
    is_completed: bool | None,
    needs_notification: bool,
) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE schedule.schedules
                SET category_id = %s, title = %s, location = %s, detail = %s,
                    kind = %s, granularity = %s, start_date = %s, end_date = %s,
                    start_time = %s, end_time = %s, is_completed = %s,
                    needs_notification = %s
                WHERE id = %s AND user_id = %s AND is_deleted = false
                """,
                (
                    category_id,
                    title,
                    location,
                    detail,
                    kind,
                    granularity,
                    start_date,
                    end_date,
                    start_time,
                    end_time,
                    is_completed,
                    needs_notification,
                    schedule_id,
                    user_id,
                ),
            )


def update_schedule_completion(schedule_id: int, user_id: int, is_completed: bool) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE schedule.schedules
                SET is_completed = %s
                WHERE id = %s AND user_id = %s AND is_deleted = false
                """,
                (is_completed, schedule_id, user_id),
            )


def logical_delete_schedule(schedule_id: int, user_id: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE schedule.schedules
                SET is_deleted = true
                WHERE id = %s AND user_id = %s AND is_deleted = false
                """,
                (schedule_id, user_id),
            )


def get_preference(user_id: int) -> PreferenceRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, week_starts_on, show_deleted
                FROM schedule.preferences
                WHERE user_id = %s
                """,
                (user_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return PreferenceRow(
                user_id=int(row["user_id"]),
                week_starts_on=str(row["week_starts_on"]),
                show_deleted=bool(row["show_deleted"]),
            )


def upsert_preference(user_id: int, week_starts_on: str, show_deleted: bool) -> PreferenceRow:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO schedule.preferences (user_id, week_starts_on, show_deleted)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE
                SET week_starts_on = EXCLUDED.week_starts_on,
                    show_deleted = EXCLUDED.show_deleted
                RETURNING user_id, week_starts_on, show_deleted
                """,
                (user_id, week_starts_on, show_deleted),
            )
            row = cur.fetchone()
            assert row is not None
            return PreferenceRow(
                user_id=int(row["user_id"]),
                week_starts_on=str(row["week_starts_on"]),
                show_deleted=bool(row["show_deleted"]),
            )


def list_hidden_category_ids(user_id: int) -> list[int]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT category_id
                FROM schedule.hidden_categories
                WHERE user_id = %s
                ORDER BY category_id
                """,
                (user_id,),
            )
            return [int(row["category_id"]) for row in cur.fetchall()]


def replace_hidden_categories(user_id: int, category_ids: list[int]) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM schedule.hidden_categories WHERE user_id = %s",
                (user_id,),
            )
            for category_id in category_ids:
                cur.execute(
                    """
                    INSERT INTO schedule.hidden_categories (user_id, category_id)
                    VALUES (%s, %s)
                    """,
                    (user_id, category_id),
                )


def _holiday_from_row(row: dict[str, object]) -> UserHolidayRow:
    return UserHolidayRow(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        holiday_date=row["holiday_date"],
        name=str(row["name"]),
        is_deleted=bool(row["is_deleted"]),
    )


def list_user_holidays(
    user_id: int,
    start_date: date | None,
    end_date: date | None,
) -> list[UserHolidayRow]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            if start_date is not None and end_date is not None:
                cur.execute(
                    """
                    SELECT id, user_id, holiday_date, name, is_deleted
                    FROM schedule.user_holidays
                    WHERE user_id = %s
                      AND is_deleted = false
                      AND holiday_date >= %s
                      AND holiday_date <= %s
                    ORDER BY holiday_date ASC
                    """,
                    (user_id, start_date, end_date),
                )
            else:
                cur.execute(
                    """
                    SELECT id, user_id, holiday_date, name, is_deleted
                    FROM schedule.user_holidays
                    WHERE user_id = %s AND is_deleted = false
                    ORDER BY holiday_date ASC
                    """,
                    (user_id,),
                )
            return [_holiday_from_row(row) for row in cur.fetchall()]


def get_user_holiday(user_id: int, holiday_id: int) -> UserHolidayRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, holiday_date, name, is_deleted
                FROM schedule.user_holidays
                WHERE id = %s AND user_id = %s
                """,
                (holiday_id, user_id),
            )
            row = cur.fetchone()
            return _holiday_from_row(row) if row else None


def insert_user_holiday(user_id: int, holiday_date: date, name: str) -> UserHolidayRow:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO schedule.user_holidays (user_id, holiday_date, name)
                VALUES (%s, %s, %s)
                RETURNING id, user_id, holiday_date, name, is_deleted
                """,
                (user_id, holiday_date, name),
            )
            row = cur.fetchone()
            assert row is not None
            return _holiday_from_row(row)


def update_user_holiday(
    holiday_id: int,
    user_id: int,
    holiday_date: date,
    name: str,
) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE schedule.user_holidays
                SET holiday_date = %s, name = %s
                WHERE id = %s AND user_id = %s AND is_deleted = false
                """,
                (holiday_date, name, holiday_id, user_id),
            )


def logical_delete_user_holiday(holiday_id: int, user_id: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE schedule.user_holidays
                SET is_deleted = true
                WHERE id = %s AND user_id = %s AND is_deleted = false
                """,
                (holiday_id, user_id),
            )


def _routine_from_row(
    row: dict[str, object],
    months: tuple[int, ...],
    exclusions: tuple[str, ...],
) -> RoutineRow:
    detail = row["detail"]
    date_rule = row["date_rule"]
    day_of_month = row["day_of_month"]
    weekday_rule = row["weekday_rule"]
    weekday_n = row["weekday_n"]
    weekday = row["weekday"]
    shift_direction = row["shift_direction"]
    return RoutineRow(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        category_id=int(row["category_id"]),
        title=str(row["title"]),
        detail=str(detail) if detail is not None else None,
        kind=str(row["kind"]),
        occurrence_type=str(row["occurrence_type"]),
        date_rule=str(date_rule) if date_rule is not None else None,
        day_of_month=int(day_of_month) if day_of_month is not None else None,
        weekday_rule=str(weekday_rule) if weekday_rule is not None else None,
        weekday_n=int(weekday_n) if weekday_n is not None else None,
        weekday=str(weekday) if weekday is not None else None,
        adjust_excluded=bool(row["adjust_excluded"]),
        shift_direction=str(shift_direction) if shift_direction is not None else None,
        needs_notification=bool(row["needs_notification"]),
        is_deleted=bool(row["is_deleted"]),
        months=months,
        exclusions=exclusions,
    )


_ROUTINE_SELECT = """
    SELECT id, user_id, category_id, title, detail, kind, occurrence_type, date_rule,
           day_of_month, weekday_rule, weekday_n, weekday, adjust_excluded,
           shift_direction, needs_notification, is_deleted
    FROM schedule.routines
"""


def _months_and_exclusions(
    cur: object,
    routine_ids: list[int],
) -> tuple[dict[int, list[int]], dict[int, list[str]]]:
    months: dict[int, list[int]] = {routine_id: [] for routine_id in routine_ids}
    exclusions: dict[int, list[str]] = {routine_id: [] for routine_id in routine_ids}
    if not routine_ids:
        return months, exclusions
    cur.execute(
        """
        SELECT routine_id, month
        FROM schedule.routine_months
        WHERE routine_id = ANY(%s)
        ORDER BY month ASC
        """,
        (routine_ids,),
    )
    for row in cur.fetchall():
        months[int(row["routine_id"])].append(int(row["month"]))
    cur.execute(
        """
        SELECT routine_id, exclusion_kind
        FROM schedule.routine_exclusions
        WHERE routine_id = ANY(%s)
        ORDER BY exclusion_kind ASC
        """,
        (routine_ids,),
    )
    for row in cur.fetchall():
        exclusions[int(row["routine_id"])].append(str(row["exclusion_kind"]))
    return months, exclusions


def list_routines(user_id: int) -> list[RoutineRow]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                _ROUTINE_SELECT
                + """
                WHERE user_id = %s AND is_deleted = false
                ORDER BY title ASC, id ASC
                """,
                (user_id,),
            )
            rows = list(cur.fetchall())
            ids = [int(row["id"]) for row in rows]
            months_map, exclusions_map = _months_and_exclusions(cur, ids)
            return [
                _routine_from_row(
                    row,
                    tuple(months_map[int(row["id"])]),
                    tuple(exclusions_map[int(row["id"])]),
                )
                for row in rows
            ]


def get_routine(user_id: int, routine_id: int) -> RoutineRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                _ROUTINE_SELECT + " WHERE id = %s AND user_id = %s",
                (routine_id, user_id),
            )
            row = cur.fetchone()
            if row is None:
                return None
            months_map, exclusions_map = _months_and_exclusions(cur, [int(row["id"])])
            return _routine_from_row(
                row,
                tuple(months_map[int(row["id"])]),
                tuple(exclusions_map[int(row["id"])]),
            )


def insert_routine(
    user_id: int,
    category_id: int,
    title: str,
    detail: str | None,
    kind: str,
    occurrence_type: str,
    date_rule: str | None,
    day_of_month: int | None,
    weekday_rule: str | None,
    weekday_n: int | None,
    weekday: str | None,
    adjust_excluded: bool,
    shift_direction: str | None,
    needs_notification: bool,
    months: list[int],
    exclusions: list[str],
) -> RoutineRow:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO schedule.routines (
                    user_id, category_id, title, detail, kind, occurrence_type, date_rule,
                    day_of_month, weekday_rule, weekday_n, weekday, adjust_excluded,
                    shift_direction, needs_notification
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, user_id, category_id, title, detail, kind, occurrence_type,
                          date_rule, day_of_month, weekday_rule, weekday_n, weekday,
                          adjust_excluded, shift_direction, needs_notification, is_deleted
                """,
                (
                    user_id,
                    category_id,
                    title,
                    detail,
                    kind,
                    occurrence_type,
                    date_rule,
                    day_of_month,
                    weekday_rule,
                    weekday_n,
                    weekday,
                    adjust_excluded,
                    shift_direction,
                    needs_notification,
                ),
            )
            row = cur.fetchone()
            assert row is not None
            routine_id = int(row["id"])
            for month in months:
                cur.execute(
                    """
                    INSERT INTO schedule.routine_months (routine_id, month)
                    VALUES (%s, %s)
                    """,
                    (routine_id, month),
                )
            for kind_value in exclusions:
                cur.execute(
                    """
                    INSERT INTO schedule.routine_exclusions (routine_id, exclusion_kind)
                    VALUES (%s, %s)
                    """,
                    (routine_id, kind_value),
                )
            return _routine_from_row(row, tuple(sorted(months)), tuple(sorted(exclusions)))


def update_routine(
    routine_id: int,
    user_id: int,
    category_id: int,
    title: str,
    detail: str | None,
    kind: str,
    occurrence_type: str,
    date_rule: str | None,
    day_of_month: int | None,
    weekday_rule: str | None,
    weekday_n: int | None,
    weekday: str | None,
    adjust_excluded: bool,
    shift_direction: str | None,
    needs_notification: bool,
    months: list[int],
    exclusions: list[str],
) -> RoutineRow | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE schedule.routines
                SET category_id = %s, title = %s, detail = %s, kind = %s, occurrence_type = %s,
                    date_rule = %s, day_of_month = %s, weekday_rule = %s, weekday_n = %s,
                    weekday = %s, adjust_excluded = %s, shift_direction = %s,
                    needs_notification = %s
                WHERE id = %s AND user_id = %s AND is_deleted = false
                RETURNING id, user_id, category_id, title, detail, kind, occurrence_type,
                          date_rule, day_of_month, weekday_rule, weekday_n, weekday,
                          adjust_excluded, shift_direction, needs_notification, is_deleted
                """,
                (
                    category_id,
                    title,
                    detail,
                    kind,
                    occurrence_type,
                    date_rule,
                    day_of_month,
                    weekday_rule,
                    weekday_n,
                    weekday,
                    adjust_excluded,
                    shift_direction,
                    needs_notification,
                    routine_id,
                    user_id,
                ),
            )
            row = cur.fetchone()
            if row is None:
                return None
            cur.execute("DELETE FROM schedule.routine_months WHERE routine_id = %s", (routine_id,))
            cur.execute("DELETE FROM schedule.routine_exclusions WHERE routine_id = %s", (routine_id,))
            for month in months:
                cur.execute(
                    """
                    INSERT INTO schedule.routine_months (routine_id, month)
                    VALUES (%s, %s)
                    """,
                    (routine_id, month),
                )
            for kind_value in exclusions:
                cur.execute(
                    """
                    INSERT INTO schedule.routine_exclusions (routine_id, exclusion_kind)
                    VALUES (%s, %s)
                    """,
                    (routine_id, kind_value),
                )
            return _routine_from_row(row, tuple(sorted(months)), tuple(sorted(exclusions)))


def logical_delete_routine(routine_id: int, user_id: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE schedule.routines
                SET is_deleted = true
                WHERE id = %s AND user_id = %s AND is_deleted = false
                """,
                (routine_id, user_id),
            )


def exists_routine_in_year_month(user_id: int, routine_id: int, year: int, month: int) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM schedule.schedules
                WHERE user_id = %s
                  AND routine_id = %s
                  AND is_deleted = false
                  AND EXTRACT(YEAR FROM start_date) = %s
                  AND EXTRACT(MONTH FROM start_date) = %s
                LIMIT 1
                """,
                (user_id, routine_id, year, month),
            )
            return cur.fetchone() is not None

