"""调度器启动与生命周期。

权威排期数据在 MySQL 的 `targets` 表里，APScheduler 只是它的投影。
本模块负责：
    1. 用文件锁保证同一台机器上只有一个调度器实例（防 --reload / 多 worker 双启动）；
    2. 启动时把数据库里的排期全量注册为 APScheduler 作业；
    3. 注册常驻的告警投递作业。
"""
import fcntl
import os
from pathlib import Path
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.logging import logger
from app.config import get_settings

#: 全局调度器实例
_scheduler: Optional[BackgroundScheduler] = None
#: 文件锁句柄，持有即代表本进程是唯一的调度器
_lock_handle = None

#: 告警投递作业的间隔（秒）
ALERT_DISPATCH_INTERVAL = 60


def _lock_path() -> Path:
    """锁文件路径：优先放在 XDG_RUNTIME_DIR，退化到 /tmp。"""
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir and Path(runtime_dir).is_dir():
        path = Path(runtime_dir) / "veeam-inspection" / "scheduler.lock"
    else:
        path = Path("/tmp") / f"veeam-inspection-scheduler-{os.getuid()}.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def acquire_lock() -> bool:
    """尝试获取独占锁；拿不到说明已有别的调度器在跑。"""
    global _lock_handle
    if _lock_handle is not None:
        return True
    handle = open(_lock_path(), "w")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return False
    _lock_handle = handle
    return True


def release_lock() -> None:
    """释放锁。"""
    global _lock_handle
    if _lock_handle is None:
        return
    try:
        fcntl.flock(_lock_handle.fileno(), fcntl.LOCK_UN)
    finally:
        _lock_handle.close()
        _lock_handle = None


def get_scheduler() -> Optional[BackgroundScheduler]:
    """取当前调度器实例。"""
    return _scheduler


def start_scheduler() -> Optional[BackgroundScheduler]:
    """启动调度器；已被别的进程占用时返回 None。"""
    global _scheduler
    settings = get_settings()
    if not settings.scheduler_enabled:
        logger.info("scheduler disabled by configuration")
        return None
    if _scheduler is not None:
        return _scheduler
    if not acquire_lock():
        logger.warning("scheduler lock held by another process, skipping start")
        return None

    from apscheduler.schedulers.background import BackgroundScheduler as _BS

    scheduler = _BS(timezone=settings.default_timezone)
    _scheduler = scheduler

    # 把数据库里的排期全量投影成作业
    from app.db.session import SessionLocal
    from app.services import scheduler_service

    with SessionLocal() as db:
        scheduler_service.reload_all(db, scheduler)

    scheduler.start()
    logger.info(
        "scheduler started",
        extra={"jobs": len(scheduler.get_jobs()), "timezone": settings.default_timezone},
    )
    return scheduler


def stop_scheduler() -> None:
    """停止调度器并释放锁。"""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
    release_lock()
