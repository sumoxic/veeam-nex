"""系统状态接口：健康检查、版本信息、调度器状态。"""
import time

from fastapi import APIRouter
from sqlalchemy import text

from app.config import get_settings
from app.db.session import engine
from app.utils.errors import ok

router = APIRouter(prefix="/system", tags=["系统"])

START_TIME = time.time()


@router.get("/health", summary="健康检查")
def health() -> dict:
    """返回数据库连通性与运行时长。"""
    settings = get_settings()
    db_ok = True
    db_error = None
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 —— 健康检查不应因异常中断
        db_ok = False
        db_error = str(exc)

    return ok(
        {
            "status": "ok" if db_ok else "degraded",
            "app": settings.app_name,
            "version": settings.app_version,
            "uptime_seconds": round(time.time() - START_TIME, 1),
            "database": {"ok": db_ok, "error": db_error, "name": settings.db_name},
        }
    )


@router.get("/info", summary="版本与配置概览")
def info() -> dict:
    """返回不含任何密钥的配置概览。"""
    settings = get_settings()
    return ok(
        {
            "app": settings.app_name,
            "version": settings.app_version,
            "database": {
                "host": settings.db_host,
                "port": settings.db_port,
                "name": settings.db_name,
            },
            "scheduler_enabled": settings.scheduler_enabled,
            "default_timezone": settings.default_timezone,
        }
    )
