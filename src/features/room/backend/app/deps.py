from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, Request

from app.config import FEATURE_ID, load_config
from app.logger import write
from app.repos import (
    UserRow,
    find_api_key_by_hash,
    get_session,
    get_user_by_id,
    get_user_by_username,
    touch_api_key_last_used,
    update_session_expiry,
)
from app.security import (
    API_KEY_PREFIX_LENGTH,
    COOKIE_NAME,
    bearer_token,
    hash_api_key,
    session_expiry,
)
from app.services.access_service import is_feature_allowed


@dataclass(frozen=True)
class AuthContext:
    """認証できた利用者。API キー認証と DEBUG_USER では session_id は None。

    via は認証の経路（`session`=Cookie、`api_key`=API キー、`debug`=DEBUG_USER）。
    操作ログの「実行した主体」の区別に使う。
    """

    user: UserRow
    session_id: UUID | None
    via: str = "session"


def _api_key_unauthenticated() -> HTTPException:
    return HTTPException(
        status_code=401, detail="未ログイン", headers={"WWW-Authenticate": "Bearer"}
    )


def _authenticate_api_key(authorization: str) -> AuthContext:
    """API キー（Authorization: Bearer）で判定する。失敗しても Cookie・DEBUG_USER へは戻らない。"""
    token = bearer_token(authorization)
    if token is None:
        write("WRN", "API キー認証失敗 理由=Bearer方式でないまたは空")
        raise _api_key_unauthenticated()

    key = find_api_key_by_hash(hash_api_key(token))
    if key is None:
        # キー全体やハッシュは出さず、識別用の先頭部分だけを出す
        write("WRN", f"API キー認証失敗 prefix={token[:API_KEY_PREFIX_LENGTH]} 理由=該当なし")
        raise _api_key_unauthenticated()
    if key.revoked_at is not None:
        write("WRN", f"API キー認証失敗 id={key.id} prefix={key.key_prefix} 理由=失効済み")
        raise _api_key_unauthenticated()
    if key.expires_at is not None and key.expires_at <= datetime.now(timezone.utc):
        write("WRN", f"API キー認証失敗 id={key.id} prefix={key.key_prefix} 理由=期限切れ")
        raise _api_key_unauthenticated()
    if key.user_is_deleted:
        write("WRN", f"API キー認証失敗 id={key.id} prefix={key.key_prefix} 理由=ユーザ削除済み")
        raise _api_key_unauthenticated()

    if not is_feature_allowed(key.user_id, FEATURE_ID):
        write(
            "WRN",
            f"API キー認可失敗 username={key.username} id={key.id} prefix={key.key_prefix} 理由=権限なし",
        )
        raise HTTPException(status_code=403, detail="権限がありません")

    # 許可したときだけ最終利用日時を更新する。セッションの期限は延ばさない
    touch_api_key_last_used(key.id)
    write("INF", f"API キー認証成功 username={key.username} id={key.id} prefix={key.key_prefix}")
    user = UserRow(id=key.user_id, username=key.username, is_deleted=False)
    return AuthContext(user=user, session_id=None, via="api_key")


def get_current_user(request: Request) -> AuthContext:
    """要求からログイン中の利用者を特定し、本機能の割当を判定する。"""
    authorization = request.headers.get("authorization")
    if authorization is not None:
        return _authenticate_api_key(authorization)

    cfg = load_config()
    if cfg.debug_user:
        user = get_user_by_username(cfg.debug_user)
        if user is None or user.is_deleted:
            write("WRN", f"認証失敗 username={cfg.debug_user} 理由=未ログイン")
            raise HTTPException(status_code=401, detail="未ログイン")
        if not is_feature_allowed(user.id, FEATURE_ID):
            write("WRN", f"認可失敗 username={user.username} 理由=権限なし")
            raise HTTPException(status_code=403, detail="権限がありません")
        return AuthContext(user=user, session_id=None, via="debug")

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
    if session is None or session.expires_at <= datetime.now(timezone.utc):
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
    return AuthContext(user=user, session_id=session_id, via="session")
