from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import load_config
from app.logger import safe_text, setup_logging, write
from app.routers.auth import router as auth_router
from app.routers.menu import router as menu_router
from app.routers.settings import router as settings_router


def _username_from_body(body: object) -> str:
    if isinstance(body, dict):
        value = body.get("username")
        if isinstance(value, str):
            return safe_text(value)
    return ""


def create_app() -> FastAPI:
    cfg = load_config()
    setup_logging()
    app = FastAPI(title="portal")
    # CORS は .env の CORS_ORIGINS（カンマ区切り）。localhost と 127.0.0.1 を両方許可する。
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router)
    app.include_router(settings_router)
    app.include_router(menu_router)

    @app.exception_handler(RequestValidationError)
    async def on_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        if request.url.path.rstrip("/") == "/auth/login":
            username = _username_from_body(exc.body)
            write("INF", f"ログイン要求 username={username}")
            write("WRN", f"ログイン失敗 username={username} 理由=入力不正")
        return JSONResponse(status_code=400, content={"detail": "入力が不正です"})

    @app.exception_handler(HTTPException)
    async def on_http(_request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "サーバエラーです"
        return JSONResponse(status_code=exc.status_code, content={"detail": detail})

    @app.exception_handler(Exception)
    async def on_error(request: Request, exc: Exception) -> JSONResponse:
        if request.url.path.rstrip("/") == "/auth/login":
            write("ERR", f"ログイン処理の想定外の失敗 type={type(exc).__name__}")
        return JSONResponse(status_code=500, content={"detail": "サーバエラーです"})

    return app


app = create_app()
