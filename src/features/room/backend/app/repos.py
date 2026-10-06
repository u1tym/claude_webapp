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
class ApiKeyAuthRow:
    id: int
    user_id: int
    key_prefix: str
    expires_at: datetime | None
    revoked_at: datetime | None
    username: str
    user_is_deleted: bool


def _user_from_row(row: dict[str, object]) -> UserRow:
    return UserRow(
        id=int(row["id"]),  # type: ignore[arg-type]
        username=str(row["username"]),
        is_deleted=bool(row["is_deleted"]),
    )


def get_user_by_username(username: str) -> UserRow | None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, username, is_deleted FROM public.users WHERE username = %s",
            (username,),
        )
        row = cur.fetchone()
        return _user_from_row(row) if row is not None else None


def get_user_by_id(user_id: int) -> UserRow | None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, username, is_deleted FROM public.users WHERE id = %s",
            (user_id,),
        )
        row = cur.fetchone()
        return _user_from_row(row) if row is not None else None


def get_session(session_id: UUID) -> SessionRow | None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, user_id, expires_at FROM public.sessions WHERE id = %s",
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
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE public.sessions SET expires_at = %s WHERE id = %s",
            (expires_at, str(session_id)),
        )


def get_setting(key: str) -> SettingRow | None:
    with get_conn() as conn, conn.cursor() as cur:
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
    with get_conn() as conn, conn.cursor() as cur:
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
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM public.menu_assignments WHERE user_id = %s AND feature_id = %s",
            (user_id, feature_id),
        )
        return cur.fetchone() is not None


# ---- api_keys（api-key-management が作成する。読み取りと last_used_at の更新だけ行う） ----


def find_api_key_by_hash(key_hash: str) -> ApiKeyAuthRow | None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT k.id, k.user_id, k.key_prefix, k.expires_at, k.revoked_at,
                   u.username, u.is_deleted
            FROM public.api_keys k
            JOIN public.users u ON u.id = k.user_id
            WHERE k.key_hash = %s
            """,
            (key_hash,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return ApiKeyAuthRow(
            id=int(row["id"]),
            user_id=int(row["user_id"]),
            key_prefix=str(row["key_prefix"]),
            expires_at=row["expires_at"],
            revoked_at=row["revoked_at"],
            username=str(row["username"]),
            user_is_deleted=bool(row["is_deleted"]),
        )


def touch_api_key_last_used(api_key_id: int) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE public.api_keys SET last_used_at = now() WHERE id = %s",
            (api_key_id,),
        )


# ---- 定期実行の定義（スキーマ room） ----


@dataclass(frozen=True)
class RoomScheduleRow:
    id: int
    created_by_user_id: int
    condition_type: str
    weekdays: tuple[int, ...]
    holiday_mode: str
    day_shift: str
    run_time: time
    action_type: str
    scene: str | None
    device: str | None
    target_state: str | None
    is_enabled: bool
    last_run_at: datetime | None
    last_run_result: str | None
    last_failed_devices: tuple[str, ...]
    # 電灯を ON にする個別切替の調光パターン。None は既定のパターン（それ以外の定期実行も None）
    dimming_pattern: str | None = None
    # 画面の一覧で見分けるための名前（任意。50 文字まで）と、並べる順（任意。0〜9999。小さい数が先、None は末尾）
    title: str | None = None
    display_order: int | None = None


_SCHEDULE_COLUMNS = """
    s.id, s.created_by_user_id, s.condition_type, s.holiday_mode, s.day_shift, s.run_time,
    s.action_type, s.scene, s.device, s.target_state, s.dimming_pattern, s.title, s.display_order, s.is_enabled,
    s.last_run_at, s.last_run_result, s.last_failed_devices,
    COALESCE(
        array_agg(w.weekday ORDER BY w.weekday) FILTER (WHERE w.weekday IS NOT NULL),
        '{}'
    ) AS weekdays
"""

_SCHEDULE_FROM = """
    FROM room.room_schedules s
    LEFT JOIN room.schedule_weekdays w ON w.schedule_id = s.id
"""


def _schedule_from_row(row: dict[str, object]) -> RoomScheduleRow:
    return RoomScheduleRow(
        id=int(row["id"]),  # type: ignore[arg-type]
        created_by_user_id=int(row["created_by_user_id"]),  # type: ignore[arg-type]
        condition_type=str(row["condition_type"]),
        weekdays=tuple(int(d) for d in row["weekdays"]),  # type: ignore[attr-defined]
        holiday_mode=str(row["holiday_mode"]),
        day_shift=str(row["day_shift"]),
        run_time=row["run_time"],  # type: ignore[arg-type]
        action_type=str(row["action_type"]),
        scene=str(row["scene"]) if row["scene"] is not None else None,
        device=str(row["device"]) if row["device"] is not None else None,
        target_state=str(row["target_state"]) if row["target_state"] is not None else None,
        is_enabled=bool(row["is_enabled"]),
        last_run_at=row["last_run_at"],  # type: ignore[arg-type]
        last_run_result=(
            str(row["last_run_result"]) if row["last_run_result"] is not None else None
        ),
        last_failed_devices=tuple(str(d) for d in row["last_failed_devices"]),  # type: ignore[attr-defined]
        dimming_pattern=str(row["dimming_pattern"]) if row["dimming_pattern"] is not None else None,
        title=str(row["title"]) if row["title"] is not None else None,
        display_order=int(row["display_order"]) if row["display_order"] is not None else None,  # type: ignore[arg-type]
    )


def list_room_schedules(only_enabled: bool = False) -> list[RoomScheduleRow]:
    """定期実行を、表示順の昇順（表示順が無いものは末尾）で返す。同じ値の中は、時刻の昇順、同じ時刻なら
    一括切替（scene 順）→ 個別切替（device、状態順）→ id 順。"""
    where = "WHERE s.is_enabled" if only_enabled else ""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT {_SCHEDULE_COLUMNS} {_SCHEDULE_FROM} {where} "
            "GROUP BY s.id ORDER BY s.display_order ASC NULLS LAST, s.run_time, "
            "(s.action_type = 'device'), s.scene, s.device, s.target_state, s.id"
        )
        return [_schedule_from_row(row) for row in cur.fetchall()]


def get_room_schedule(schedule_id: int) -> RoomScheduleRow | None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT {_SCHEDULE_COLUMNS} {_SCHEDULE_FROM} WHERE s.id = %s GROUP BY s.id",
            (schedule_id,),
        )
        row = cur.fetchone()
        return _schedule_from_row(row) if row is not None else None


def _replace_weekdays(cur: object, schedule_id: int, weekdays: tuple[int, ...]) -> None:
    cur.execute("DELETE FROM room.schedule_weekdays WHERE schedule_id = %s", (schedule_id,))  # type: ignore[attr-defined]
    for weekday in weekdays:
        cur.execute(  # type: ignore[attr-defined]
            "INSERT INTO room.schedule_weekdays (schedule_id, weekday) VALUES (%s, %s)",
            (schedule_id, weekday),
        )


@dataclass(frozen=True)
class ScheduleDefinition:
    """定期実行の定義（最終実行を除く）。action_type に応じて scene か device+target_state を持つ。"""

    condition_type: str
    weekdays: tuple[int, ...]
    holiday_mode: str
    day_shift: str
    run_time: time
    action_type: str
    scene: str | None
    device: str | None
    target_state: str | None
    # 電灯を ON にする個別切替の調光パターン。None は既定のパターン（それ以外の定期実行も None）
    dimming_pattern: str | None = None
    # タイトルと表示順。None は「付けない」（登録）、または「外す」（変更で、書き換えるとき）
    title: str | None = None
    display_order: int | None = None
    # 変更で、タイトルと表示順を書き換えるか。False なら、現在の値を変えない（要求に項目が無かったとき）。
    # 登録では使わない（常に、title・display_order の値で登録する）
    update_title: bool = True
    update_display_order: bool = True


def insert_room_schedule(user_id: int, definition: ScheduleDefinition, is_enabled: bool) -> int:
    """定期実行と曜日を 1 つのトランザクションで登録し、識別子を返す。"""
    d = definition
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO room.room_schedules
                (created_by_user_id, condition_type, holiday_mode, day_shift, run_time,
                 action_type, scene, device, target_state, dimming_pattern, title, display_order, is_enabled)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                user_id, d.condition_type, d.holiday_mode, d.day_shift, d.run_time,
                d.action_type, d.scene, d.device, d.target_state, d.dimming_pattern,
                d.title, d.display_order, is_enabled,
            ),
        )
        row = cur.fetchone()
        assert row is not None
        schedule_id = int(row["id"])
        _replace_weekdays(cur, schedule_id, d.weekdays)
        return schedule_id


def update_room_schedule(
    schedule_id: int, definition: ScheduleDefinition, is_enabled: bool | None
) -> bool:
    """定義を置き換える（最終実行は変えない）。is_enabled が None なら現在の値を保つ。

    タイトルと表示順は、update_title・update_display_order が True のときだけ書き換える（False なら、現在の値のまま）。
    """
    d = definition
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE room.room_schedules
            SET condition_type = %s, holiday_mode = %s, day_shift = %s, run_time = %s,
                action_type = %s, scene = %s, device = %s, target_state = %s, dimming_pattern = %s,
                title = CASE WHEN %s THEN %s ELSE title END,
                display_order = CASE WHEN %s THEN %s::integer ELSE display_order END,
                is_enabled = COALESCE(%s, is_enabled), updated_at = now()
            WHERE id = %s
            """,
            (
                d.condition_type, d.holiday_mode, d.day_shift, d.run_time,
                d.action_type, d.scene, d.device, d.target_state, d.dimming_pattern,
                d.update_title, d.title, d.update_display_order, d.display_order, is_enabled, schedule_id,
            ),
        )
        if cur.rowcount == 0:
            return False
        _replace_weekdays(cur, schedule_id, d.weekdays)
        return True


def set_room_schedule_enabled(schedule_id: int, is_enabled: bool) -> bool:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE room.room_schedules SET is_enabled = %s, updated_at = now() WHERE id = %s",
            (is_enabled, schedule_id),
        )
        return bool(cur.rowcount)


def delete_room_schedule(schedule_id: int) -> bool:
    """物理削除する。曜日と実行記録は ON DELETE CASCADE で連動して消える。"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM room.room_schedules WHERE id = %s", (schedule_id,))
        return bool(cur.rowcount)


def insert_schedule_run(schedule_id: int, run_date: date) -> bool:
    """実行の記録を追加する。既にあるときは追加せず False（重複実行の防止）。"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO room.schedule_runs (schedule_id, run_date)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (schedule_id, run_date),
        )
        return cur.rowcount == 1


def update_last_run(
    schedule_id: int, at: datetime, result: str, failed_devices: tuple[str, ...]
) -> None:
    """最終実行（日時、結果、失敗した機器）を更新する。定義の項目は変えない。"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE room.room_schedules
            SET last_run_at = %s, last_run_result = %s, last_failed_devices = %s
            WHERE id = %s
            """,
            (at, result, list(failed_devices), schedule_id),
        )


def is_user_holiday(user_id: int, day: date) -> bool:
    """利用者のユーザ休日（public.user_holidays の未削除の行。読み取りのみ）に当たる日かを返す。"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM public.user_holidays "
            "WHERE user_id = %s AND holiday_date = %s AND is_deleted = false LIMIT 1",
            (user_id, day),
        )
        return cur.fetchone() is not None
