from __future__ import annotations

import psycopg2
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import load_config
from app.errors import AppError
from app.logger import setup_logging, write
from app.routers.ingredients import router as ingredients_router
from app.routers.measurements import router as measurements_router
from app.routers.recipes import router as recipes_router
from app.routers.settings import router as settings_router


def create_app() -> FastAPI:
    cfg = load_config()
    setup_logging()
    app = FastAPI(title="recipe-management", redirect_slashes=False)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(settings_router)
    app.include_router(ingredients_router)
    app.include_router(measurements_router)
    app.include_router(recipes_router)

    @app.exception_handler(RequestValidationError)
    async def on_validation(request: Request, _exc: RequestValidationError) -> JSONResponse:
        write("WRN", f"入力不正 path={request.url.path}")
        return JSONResponse(status_code=400, content={"detail": "入力が不正です"})

    @app.exception_handler(AppError)
    async def on_app_error(request: Request, exc: AppError) -> JSONResponse:
        level = "ERR" if exc.status_code >= 500 else "WRN"
        write(level, f"失敗 path={request.url.path} status={exc.status_code} 理由={exc.reason or exc.detail}")
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(StarletteHTTPException)
    async def on_http(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "サーバエラーです"
        if exc.status_code == 404:
            detail = "対象がありません"
        if exc.status_code == 405:
            detail = "入力が不正です"
        return JSONResponse(status_code=exc.status_code, content={"detail": detail})

    @app.exception_handler(Exception)
    async def on_error(request: Request, exc: Exception) -> JSONResponse:
        detail = ""
        if isinstance(exc, psycopg2.Error):
            # DB の失敗は原因（接続先・認証・権限など）が分かるよう、先頭の 1 行を残す（パスワードは含まれない）
            lines = str(exc).strip().splitlines()
            detail = f" 内容={lines[0]}" if lines else ""
        write("ERR", f"想定外の失敗 path={request.url.path} type={type(exc).__name__}{detail}")
        return JSONResponse(status_code=500, content={"detail": "サーバエラーです"})

    return app


app = create_app()
