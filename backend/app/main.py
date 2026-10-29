"""FastAPI 应用入口。

负责：应用工厂、请求链路追踪、统一异常处理、路由挂载、调度器生命周期。
"""
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.config import get_settings
from app.core.logging import bind_context, clear_context, logger, request_id_var, setup_logging
from app.utils.errors import (
    CODE_INTERNAL,
    CODE_VALIDATION,
    AppError,
    error_response,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动调度器，退出时关闭。"""
    setup_logging()
    logger.info(
        "application starting",
        extra={"app": settings.app_name, "version": settings.app_version},
    )

    from app.db.session import SessionLocal
    from app.db.seed import run_all
    from app.scheduler.bootstrap import start_scheduler, stop_scheduler

    with SessionLocal() as db:
        seed_stats = run_all(db)
    logger.info("seed data ensured", extra=seed_stats)

    scheduler = start_scheduler()

    try:
        yield
    finally:
        stop_scheduler()
        logger.info("application stopped")


def create_app() -> FastAPI:
    """创建并配置 FastAPI 实例。"""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Veeam VBR 13 备份巡检平台",
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        """为每个请求分配 request_id，并记录访问日志。"""
        rid = request.headers.get("X-Request-Id") or uuid.uuid4().hex
        request_id_var.set(rid)
        bind_context(request_id=rid, path=request.url.path)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "request completed",
                extra={
                    "method": request.method,
                    "status_code": getattr(locals().get("response", None), "status_code", 0),
                    "elapsed_ms": round(elapsed_ms, 2),
                    "client": request.client.host if request.client else "-",
                },
            )
            clear_context()
        response.headers["X-Request-Id"] = rid
        return response

    # ---------------------------------------------------------- 异常处理
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        logger.warning("business error", extra={"detail": exc.message, "code": exc.code})
        return error_response(exc.code, exc.message, exc.http_status)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        return error_response(
            CODE_VALIDATION,
            f"参数校验失败: {exc.errors()[:3]}",
            422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException):
        return error_response(exc.status_code * 100, str(exc.detail), exc.status_code)

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        logger.opt(exception=True).error("unhandled exception", extra={"path": request.url.path})
        return error_response(CODE_INTERNAL, f"服务内部错误: {exc}", 500)

    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
