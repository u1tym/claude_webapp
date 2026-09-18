from __future__ import annotations

from uuid import UUID

from app.config import load_config
from app.logger import safe_text, write
from app.repos import (
    UserRow,
    delete_session,
    get_user_by_username,
    insert_session,
)
from app.security import hash_password, new_session_id, session_expiry, verify_password


class LoginFailedError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def authenticate(username: str, password: str) -> tuple[UserRow, UUID]:
    logged_name = safe_text(username)
    user = get_user_by_username(username)
    if user is None:
        write("WRN", f"ログイン失敗 username={logged_name} 理由=ユーザなし")
        raise LoginFailedError("ユーザなし")
    if user.is_deleted:
        write("WRN", f"ログイン失敗 username={logged_name} 理由=論理削除")
        raise LoginFailedError("論理削除")
    if not verify_password(password, user.password_hash):
        write("WRN", f"ログイン失敗 username={logged_name} 理由=パスワード不一致")
        raise LoginFailedError("パスワード不一致")
    cfg = load_config()
    session_id = new_session_id()
    insert_session(session_id, user.id, session_expiry(cfg.session_timeout_minutes))
    write("INF", f"ログイン成功 username={logged_name}")
    return user, session_id


def logout(session_id: UUID) -> None:
    delete_session(session_id)


def hash_new_password(password: str) -> str:
    return hash_password(password)
