"""排期服务：把 MySQL 中的权威排期投影成 APScheduler 作业。

排期数据只存在 `targets` 表里，任何改动都要落到数据库后再调用
`sync_target_schedule` 同步作业，避免出现两个数据源。
"""
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.target import Target


def job_id(target_id: int) -> str:
    """巡检作业的 APScheduler id。"""
    return f"inspect:{target_id}"


def _build_trigger(cron: str, timezone: str) -> CronTrigger:
    """构造 cron 触发器；非法 cron 抛 ValueError。"""
    return CronTrigger.from_crontab(cron, timezone=timezone)


def sync_target_schedule(target: Target, scheduler: Optional[BackgroundScheduler] = None) -> bool:
    """按目标当前的排期配置同步作业；返回是否成功注册。"""
    from app.scheduler.bootstrap import get_scheduler

    scheduler = scheduler or get_scheduler()
    if scheduler is None:
        return False

    jid = job_id(target.id)
    existing = scheduler.get_job(jid)
    if existing is not None:
        scheduler.remove_job(jid)

    if not target.schedule_enabled or not target.schedule_cron:
        logger.info("inspection schedule removed", extra={"target_id": target.id})
        return False

    try:
        trigger = _build_trigger(target.schedule_cron, target.schedule_timezone)
    except ValueError as exc:
        logger.error(
            "invalid cron expression, schedule skipped",
            extra={"target_id": target.id, "cron": target.schedule_cron, "error": str(exc)},
        )
        return False

    scheduler.add_job(
        _run_inspection,
        trigger=trigger,
        id=jid,
        args=[target.id],
        replace_existing=True,
        coalesce=True,          # 错过多次只补跑一次
        max_instances=1,        # 同一目标不并发巡检
        misfire_grace_time=3600,
        name=f"巡检 {target.name}",
    )
    logger.info(
        "inspection schedule synced",
        extra={
            "target_id": target.id,
            "cron": target.schedule_cron,
            "timezone": target.schedule_timezone,
        },
    )
    return True


def _run_inspection(target_id: int) -> None:
    """作业包装：APScheduler 的 job 必须是可导入的顶层函数。"""
    from app.scheduler.jobs import inspection_job

    inspection_job(target_id)


def remove_target_schedule(target_id: int, scheduler: Optional[BackgroundScheduler] = None) -> None:
    """移除某目标的巡检作业。"""
    from app.scheduler.bootstrap import get_scheduler

    scheduler = scheduler or get_scheduler()
    if scheduler is None:
        return
    jid = job_id(target_id)
    if scheduler.get_job(jid) is not None:
        scheduler.remove_job(jid)
        logger.info("inspection schedule removed", extra={"target_id": target_id})


def reload_all(db: Session, scheduler: BackgroundScheduler) -> int:
    """启动时把数据库里所有启用排期的目标注册成作业。"""
    from app.scheduler.bootstrap import ALERT_DISPATCH_INTERVAL
    from app.scheduler.jobs import dispatch_alerts_job

    targets = db.scalars(
        select(Target).where(
            Target.is_enabled.is_(True),
            Target.schedule_enabled.is_(True),
            Target.schedule_cron.is_not(None),
        )
    ).all()

    count = 0
    for target in targets:
        if sync_target_schedule(target, scheduler):
            count += 1

    # 常驻作业：每分钟排空一次告警队列
    if scheduler.get_job("dispatch-alerts") is None:
        scheduler.add_job(
            dispatch_alerts_job,
            trigger="interval",
            seconds=ALERT_DISPATCH_INTERVAL,
            id="dispatch-alerts",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            name="告警投递",
        )
    return count
