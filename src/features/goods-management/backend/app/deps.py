from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, Request

from app.config import FEATURE_ID, load_config
from app.logger import write
from app.repos import UserRow, get_session, get_user_by_id, get_user_by_username, update_session_expiry
from app.security import COOKIE_NAME, session_expiry
from app.services.access_service import is_feature_allowed


@dataclass(frozen=True)
class AuthContext:
    user: UserRow
    session_id: UUID | None


def get_current_user(request: Request) -> AuthContext:
    cfg = load_config()
    if cfg.debug_user:
        user = get_user_by_username(cfg.debug_user)
        if user is None or user.is_deleted:
            write("WRN", f"認証失敗 username={cfg.debug_user} 理由=未ログイン")
            raise HTTPException(status_code=401, detail="未ログイン")
        if not is_feature_allowed(user.id, FEATURE_ID):
            write("WRN", f"認可失敗 username={user.username} 理由=権限なし")
            raise HTTPException(status_code=403, detail="権限がありません")
        return AuthContext(user=user, session_id=None)

    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        write("WRN", "認証失敗 理由=未ログイン")
        raise HTTPException(status_code=401, detail="未ログイン")
    try:
        session_id = UUID(raw)
    except ValueError:
        write("WRN", "認証失敗 理由=未ログイン")
        raise HTTPException(status_code=401, detail="未ログイン") from None

    session = get_session(session_id)
    if session is None:
        write("WRN", "認証失敗 理由=未ログイン")
        raise HTTPException(status_code=401, detail="未ログイン")
    if session.expires_at <= datetime.now(timezone.utc):
        write("WRN", "認証失敗 理由=未ログイン")
        raise HTTPException(status_code=401, detail="未ログイン")

    user = get_user_by_id(session.user_id)
    if user is None or user.is_deleted:
        write("WRN", "認証失敗 理由=未ログイン")
        raise HTTPException(status_code=401, detail="未ログイン")

    if not is_feature_allowed(user.id, FEATURE_ID):
        write("WRN", f"認可失敗 username={user.username} 理由=権限なし")
        raise HTTPException(status_code=403, detail="権限がありません")

    update_session_expiry(session_id, session_expiry(cfg.session_timeout_minutes))
    return AuthContext(user=user, session_id=session_id)
