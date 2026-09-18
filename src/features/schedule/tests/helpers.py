from __future__ import annotations

from uuid import UUID, uuid4

from app.db import get_conn
from app.security import session_expiry

PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


def unique(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


def insert_user(username: str) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.users (username, password_hash)
                VALUES (%s, %s)
                RETURNING id
                """,
                (username, "x"),
            )
            row = cur.fetchone()
            assert row is not None
            return int(row["id"])


def insert_session(user_id: int, timeout_minutes: int) -> UUID:
    session_id = uuid4()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.sessions (id, user_id, expires_at)
                VALUES (%s, %s, %s)
                """,
                (str(session_id), user_id, session_expiry(timeout_minutes)),
            )
    return session_id


def ensure_feature() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM public.features WHERE id = %s", ("schedule",))
            if cur.fetchone() is not None:
                return
            cur.execute(
                """
                INSERT INTO public.features (id, title, url, icon, icon_media_type)
                VALUES (%s, %s, %s, %s, %s)
                """,
                ("schedule", "カレンダー", "http://localhost:5175/portal_schedule/", PNG_1X1, "image/png"),
            )


def assign_feature(user_id: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.menu_assignments (user_id, feature_id, display_order)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, feature_id) DO NOTHING
                """,
                (user_id, "schedule", 1),
            )
