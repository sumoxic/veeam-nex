"""调度作业入口。

所有作业自己开数据库会话、跑完就关，绝不持有 ORM 对象跨线程。
作业载荷只允许放基本类型（target_id 之类），不放 ORM 对象、不放解密后的口令。
"""
from app.core.logging import logger
from app.db.session import SessionLocal
from app.models.inspection import RunTrigger
from app.services import inspection_service


def inspection_job(target_id: int, trigger_type: str = RunTrigger.SCHEDULE.value,
                   run_id: int | None = None) -> None:
    """定时巡检作业。"""
    logger.info("scheduled inspection started", extra={"target_id": target_id})
    inspection_service.run_inspection_job(target_id, trigger_type, run_id=run_id)


def dispatch_alerts_job() -> None:
    """告警投递作业：排空 pending 队列。"""
    from app.notifications import dispatcher

    with SessionLocal() as db:
        stats = dispatcher.dispatch_pending(db)
    if stats["total"]:
        logger.info("alert dispatch finished", extra=stats)


def cleanup_job(retention_days: int) -> None:
    """清理过期巡检记录（发现项与指纹历史保留）。"""
    from datetime import timedelta

    from sqlalchemy import delete

    from app.models.inspection import InspectionRun
    from app.utils.timeutil import to_utc_naive, utcnow

    cutoff = to_utc_naive(utcnow()) - timedelta(days=retention_days)
    with SessionLocal() as db:
        result = db.execute(delete(InspectionRun).where(InspectionRun.started_at < cutoff))
        db.commit()
    logger.info("old inspection runs cleaned", extra={"deleted": result.rowcount})
