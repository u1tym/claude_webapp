from __future__ import annotations

import psycopg2
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import load_config
from app.errors import ConflictError, InvalidInputError, NotFoundError
from app.logger import setup_logging, write
from app.routers.cancellation import router as cancellation_router
from app.routers.categories import router as categories_router
from app.routers.contracts import router as contracts_router
from app.routers.credentials import router as credentials_router
from app.routers.settings import router as settings_router


def create_app() -> FastAPI:
    cfg = load_config()
    setup_logging()
    app = FastAPI(title="contract-management", redirect_slashes=False)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(cancellation_router)
    app.include_router(categories_router)
    app.include_router(contracts_router)
    app.include_router(credentials_router)
    app.include_router(settings_router)

    @app.exception_handler(RequestValidationError)
    async def on_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        # 理由は、項目の位置と種類だけを出す（入力された値は、パスワードなどを含みうるので出さない）
        reasons = ",".join(
            f"{'.'.join(str(part) for part in err.get('loc', ()))}:{err.get('type', '')}" for err in exc.errors()
        )
        write("WRN", f"入力不正 {request.method} {request.url.path} 理由={reasons}")
        return JSONResponse(status_code=400, content={"detail": "入力が不正です"})

    @app.exception_handler(InvalidInputError)
    async def on_invalid(_request: Request, exc: InvalidInputError) -> JSONResponse:
        write("WRN", f"入力不正 理由={exc}")
        return JSONResponse(status_code=400, content={"detail": "入力が不正です"})

    @app.exception_handler(NotFoundError)
    async def on_not_found(_request: Request, exc: NotFoundError) -> JSONResponse:
        write("WRN", f"対象なし 理由={exc}")
        return JSONResponse(status_code=404, content={"detail": "対象がありません"})

    @app.exception_handler(ConflictError)
    async def on_conflict(_request: Request, exc: ConflictError) -> JSONResponse:
        write("WRN", f"競合 理由={exc}")
        return JSONResponse(status_code=409, content={"detail": "保存できませんでした"})

    @app.exception_handler(HTTPException)
    async def on_http(_request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "サーバエラーです"
        return JSONResponse(
            status_code=exc.status_code, content={"detail": detail}, headers=exc.headers
        )

    @app.exception_handler(Exception)
    async def on_error(request: Request, exc: Exception) -> JSONResponse:
        # DB の失敗は、原因の先頭の 1 行だけを出す（2 行目以降は、行の値を含みうる）
        cause = ""
        if isinstance(exc, psycopg2.Error):
            first_line = (str(exc).strip().splitlines() or [""])[0]
            cause = f" pgcode={exc.pgcode} 原因={first_line}"
        write("ERR", f"想定外の失敗 {request.method} {request.url.path} type={type(exc).__name__}{cause}")
        return JSONResponse(status_code=500, content={"detail": "サーバエラーです"})

    return app


app = create_app()
