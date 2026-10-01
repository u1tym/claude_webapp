from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from app.db import get_conn
from app.security import hash_api_key, session_expiry

PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


# このテストの実行で作ったユーザの ID。実行の最後に、conftest が関連データごと片付ける
CREATED_USER_IDS: list[int] = []


def unique(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


def insert_user(username: str, is_deleted: bool = False) -> int:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.users (username, password_hash, is_deleted)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (username, "x", is_deleted),
        )
        row = cur.fetchone()
        assert row is not None
        user_id = int(row["id"])
    CREATED_USER_IDS.append(user_id)
    return user_id


def insert_session(user_id: int, timeout_minutes: int) -> UUID:
    session_id = uuid4()
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO public.sessions (id, user_id, expires_at) VALUES (%s, %s, %s)",
            (str(session_id), user_id, session_expiry(timeout_minutes)),
        )
    return session_id


def set_session_expiry(session_id: UUID, expires_at: datetime) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE public.sessions SET expires_at = %s WHERE id = %s",
            (expires_at, str(session_id)),
        )


def get_session_expiry(session_id: UUID) -> datetime:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT expires_at FROM public.sessions WHERE id = %s", (str(session_id),))
        row = cur.fetchone()
        assert row is not None
        return row["expires_at"]


def ensure_feature() -> None:
    """機能マスタに room がなければ登録する（開発用 DB）。"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM public.features WHERE id = %s", ("room",))
        if cur.fetchone() is not None:
            return
        cur.execute(
            """
            INSERT INTO public.features (id, title, url, icon, icon_media_type)
            VALUES (%s, %s, %s, %s, %s)
            """,
            ("room", "ROOM", "http://localhost:5185/portal_room/", PNG_1X1, "image/png"),
        )


def assign_feature(user_id: int) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.menu_assignments (user_id, feature_id, display_order)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, feature_id) DO NOTHING
            """,
            (user_id, "room", 1),
        )


def insert_api_key(
    user_id: int,
    key: str,
    *,
    expired: bool = False,
    revoked: bool = False,
) -> int:
    """API キーを登録する。キー全体は保存せず、SHA-256 だけを保存する。"""
    created_at = datetime.now(timezone.utc) - timedelta(days=2)
    expires_at = created_at + timedelta(days=1) if expired else None
    revoked_at = created_at + timedelta(hours=1) if revoked else None
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.api_keys
                (user_id, name, key_hash, key_prefix, created_at, expires_at, revoked_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (user_id, "test", hash_api_key(key), key[:12], created_at, expires_at, revoked_at),
        )
        row = cur.fetchone()
        assert row is not None
        return int(row["id"])


def get_api_key_last_used(api_key_id: int) -> datetime | None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT last_used_at FROM public.api_keys WHERE id = %s", (api_key_id,))
        row = cur.fetchone()
        assert row is not None
        return row["last_used_at"]
