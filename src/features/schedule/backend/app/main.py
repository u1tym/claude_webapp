from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import load_config
from app.logger import setup_logging, write
from app.routers.categories import router as category_router
from app.routers.holidays import router as holiday_router
from app.routers.preferences import router as preference_router
from app.routers.routines import router as routine_router
from app.routers.schedules import router as schedule_router
from app.routers.settings import router as settings_router
from app.routers.user_holidays import router as user_holiday_router


def create_app() -> FastAPI:
    cfg = load_config()
    setup_logging()
    app = FastAPI(title="schedule", redirect_slashes=False)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(settings_router)
    app.include_router(schedule_router)
    app.include_router(category_router)
    app.include_router(preference_router)
    app.include_router(holiday_router)
    app.include_router(user_holiday_router)
    app.include_router(routine_router)

    @app.exception_handler(RequestValidationError)
    async def on_validation(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        write("WRN", "入力不正")
        return JSONResponse(status_code=400, content={"detail": "入力が不正です"})

    @app.exception_handler(HTTPException)
    async def on_http(_request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "サーバエラーです"
        return JSONResponse(status_code=exc.status_code, content={"detail": detail})

    @app.exception_handler(Exception)
    async def on_error(_request: Request, exc: Exception) -> JSONResponse:
        write("ERR", f"想定外の失敗 type={type(exc).__name__}")
        return JSONResponse(status_code=500, content={"detail": "サーバエラーです"})

    return app


app = create_app()
