from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, field_validator

from app.config import load_config
from app.deps import AuthContext, get_current_user
from app.logger import safe_text, write
from app.security import clear_session_cookie, set_session_cookie
from app.services.auth_service import LoginFailedError, authenticate, logout

router = APIRouter(prefix="/auth")


class LoginBody(BaseModel):
    username: str
    password: str

    @field_validator("username", "password")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("blank")
        return value


@router.post("/login", status_code=204)
def login(body: LoginBody, request: Request, response: Response) -> None:
    write("INF", f"ログイン要求 username={safe_text(body.username)}")
    try:
        _user, session_id = authenticate(body.username, body.password)
    except LoginFailedError:
        raise HTTPException(status_code=401, detail="ログインできませんでした") from None
    cfg = load_config()
    set_session_cookie(
        response,
        session_id,
        cfg.session_timeout_minutes,
        secure=request.url.scheme == "https",
    )


@router.post("/logout", status_code=204)
def do_logout(
    request: Request,
    response: Response,
    auth: AuthContext = Depends(get_current_user),
) -> None:
    if auth.session_id is not None:
        logout(auth.session_id)
    clear_session_cookie(response, secure=request.url.scheme == "https")


@router.get("/session")
def session(auth: AuthContext = Depends(get_current_user)) -> dict[str, str]:
    return {"username": auth.user.username}
