"""巡检编排：采集 → 规则求值 → 落库 → 指纹去重 → 告警分发。

一次巡检的完整生命周期都在这里，HTTP 请求与调度作业共用同一入口。
"""
import json
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.db.session import SessionLocal
from app.models.inspection import (
    ClockSource,
    InspectionRun,
    JobSnapshot,
    RepoSnapshot,
    RestorePointSnapshot,
    RunStatus,
    RunTrigger,
)
from app.models.target import Target
from app.services import finding_service, rule_service, target_service
from app.utils.timeutil import age_hours as compute_age_hours
from app.utils.timeutil import parse_iso, to_utc_naive, utcnow
from app.vbr import collector, engine
from app.vbr.context import InspectionContext

#: 原始清单落库前的体积上限
MAX_INVENTORY_BYTES = 1024 * 1024


def _trim_inventory(inventory: dict) -> dict:
    """裁剪过大的原始清单，避免单行 JSON 撑爆表空间。"""
    payload = json.dumps(inventory, ensure_ascii=False, default=str)
    if len(payload.encode("utf-8")) <= MAX_INVENTORY_BYTES:
        return inventory
    trimmed = dict(inventory)
    # 还原点与会话明细最容易膨胀，优先裁剪这两类
    for key in ("restorePoints", "sessions", "taskSessions"):
        if key in trimmed and isinstance(trimmed[key], list):
            trimmed[key] = trimmed[key][:50]
    return trimmed


def _persist_snapshots(db: Session, run: InspectionRun, inventory: dict,
                       now: datetime, vbr_now: datetime) -> None:
    """写入趋势快照表。

    `now` 是平台 UTC 时间（落库的观测时刻）；
    `vbr_now` 是 VBR 服务器时钟（所有时长计算的时间基准）。
    """
    # ---- 仓库容量 ----
    for repo in inventory.get("repositories") or []:
        capacity = repo.get("capacityGB")
        free = repo.get("freeGB")
        percent = None
        if capacity and free is not None:
            percent = free / capacity * 100
        db.add(
            RepoSnapshot(
                target_id=run.target_id,
                run_id=run.id,
                repository_id=repo.get("id") or "",
                repository_name=repo.get("name"),
                repository_path=repo.get("path"),
                capacity_gb=capacity,
                free_gb=free,
                used_space_gb=repo.get("usedSpaceGB"),
                free_percent=percent,
                is_online=repo.get("isOnline"),
                is_out_of_date=repo.get("isOutOfDate"),
                observed_at=now,
            )
        )

    # ---- 作业状态 ----
    job_configs = {c.get("id"): c for c in (inventory.get("jobConfigs") or [])}
    for job in inventory.get("jobs") or []:
        config = job_configs.get(job.get("id"), {})
        db.add(
            JobSnapshot(
                target_id=run.target_id,
                run_id=run.id,
                job_id=job.get("id") or "",
                job_name=job.get("name"),
                job_type=job.get("type"),
                status=job.get("status"),
                last_result=job.get("lastResult"),
                # 注意：这是 VBR 时钟的值，与 observed_at 不同源
                last_run_at=to_utc_naive(parse_iso(job.get("lastRun")) or utcnow())
                if job.get("lastRun")
                else None,
                next_run=to_utc_naive(parse_iso(job.get("nextRun")) or utcnow())
                if job.get("nextRun")
                else None,
                next_run_policy=job.get("nextRunPolicy"),
                is_disabled=bool(config.get("isDisabled")),
                objects_count=job.get("objectsCount"),
                progress_percent=job.get("progressPercent"),
                observed_at=now,
            )
        )

    # ---- 还原点时效 ----
    # 时长计算必须用 VBR 时钟（vbr_now），不能用平台时钟：
    # 还原点的 creationTime 带 VBR 本地时区，与 UTC 平台时间直接相减会算错。
    ctx = InspectionContext(inventory=inventory, now=vbr_now)
    for obj in ctx.restore_point_objects():
        rp = obj.get("restore_point") or {}
        created = parse_iso(rp.get("creationTime"))
        age_hours = compute_age_hours(vbr_now, created)
        db.add(
            RestorePointSnapshot(
                target_id=run.target_id,
                run_id=run.id,
                object_id=rp.get("platformId"),
                object_name=obj.get("name"),
                restore_point_id=rp.get("id"),
                creation_time=to_utc_naive(created) if created else None,
                age_hours=age_hours,
                malware_status=rp.get("malwareStatus"),
                original_size=rp.get("originalSize"),
                gfs_periods=",".join(rp.get("gfsPeriods") or []) or None,
                observed_at=now,
            )
        )


def run_inspection(
    db: Session,
    target_id: int,
    trigger_type: str = RunTrigger.MANUAL.value,
    run_id: Optional[int] = None,
) -> InspectionRun:
    """执行一次巡检并落库，返回运行记录。

    `run_id` 非空表示沿用一条已存在的运行记录（HTTP 立即返回 run_id、
    由调度器在后台补跑的场景）。
    """
    target = db.get(Target, target_id)
    if target is None:
        from app.utils.errors import NotFoundError

        raise NotFoundError(f"巡检目标 {target_id} 不存在")

    started = to_utc_naive(utcnow())
    if run_id is not None:
        run = db.get(InspectionRun, run_id)
        if run is None:
            from app.utils.errors import NotFoundError

            raise NotFoundError(f"巡检运行记录 {run_id} 不存在")
        run.trigger_type = trigger_type
        run.status = RunStatus.RUNNING
        run.started_at = started
    else:
        run = InspectionRun(
            target_id=target_id,
            trigger_type=trigger_type,
            status=RunStatus.RUNNING,
            started_at=started,
            clock_source=ClockSource.PLATFORM,
            created_at=started,
        )
        db.add(run)
    db.commit()
    db.refresh(run)

    logger.info(
        "inspection run started",
        extra={"target_id": target_id, "run_id": run.id, "trigger": trigger_type},
    )

    try:
        client = target_service.build_client(target)
        result = collector.collect(client)
    except Exception as exc:  # noqa: BLE001 —— 采集失败要把轮次标记为失败
        run.status = RunStatus.FAILED
        run.finished_at = to_utc_naive(utcnow())
        run.duration_ms = int((run.finished_at - started).total_seconds() * 1000)
        run.error_message = str(exc)[:2000]
        db.commit()
        logger.error(
            "inspection run failed",
            extra={"target_id": target_id, "run_id": run.id, "error": str(exc)},
        )
        db.refresh(run)
        return run

    # ---- 规则求值 ----
    config = rule_service.effective_config(db, target_id)
    ctx = InspectionContext(
        inventory=result.inventory,
        now=result.now,
        clock_source=result.clock_source,
        config=config,
    )
    findings, rule_errors = engine.run(ctx)
    errors = list(result.errors) + rule_errors

    # ---- 落库：趋势快照 ----
    # 快照或发现项落库失败不算「整轮巡检失败」，但必须让本轮状态变成 partial，
    # 否则运行记录会显示成功而实际没有数据。
    finished = to_utc_naive(utcnow())
    try:
        _persist_snapshots(db, run, result.inventory, finished, result.now)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        errors.append(f"快照落库失败: {exc}")
        logger.error(
            "snapshot persistence failed",
            extra={"target_id": target_id, "run_id": run.id, "error": str(exc)},
        )

    # ---- 发现项去重与状态流转 ----
    hit: list = []
    resolved: list = []
    try:
        hit, resolved = finding_service.sync_findings(
            db, target_id, run.id, findings, now=finished
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        errors.append(f"发现项落库失败: {exc}")
        logger.error(
            "finding sync failed",
            extra={"target_id": target_id, "run_id": run.id, "error": str(exc)},
        )

    # ---- 运行记录落库（放在最后，状态才反映真实结果）----
    run.status = RunStatus.PARTIAL if errors else RunStatus.SUCCESS
    run.finished_at = finished
    run.duration_ms = int((finished - started).total_seconds() * 1000)
    run.clock_source = (
        ClockSource.VBR if result.clock_source == "vbr" else ClockSource.PLATFORM
    )
    run.vbr_server_time = to_utc_naive(result.now)
    run.vbr_build = result.server_build
    run.error_count = len(errors)
    run.error_message = "; ".join(errors)[:2000] if errors else None
    run.inventory_json = _trim_inventory(result.inventory)
    run.findings_total = len(findings)
    run.findings_critical = sum(1 for f in findings if f.level == "critical")
    run.findings_warn = sum(1 for f in findings if f.level == "warn")
    run.findings_info = sum(1 for f in findings if f.level == "info")
    db.commit()
    db.refresh(run)

    # ---- 告警分发 ----
    try:
        from app.services import alert_service

        alert_service.dispatch_for_run(db, run, hit, resolved)
    except Exception as exc:  # noqa: BLE001 —— 告警失败不影响巡检结果
        logger.warning(
            "alert dispatch failed",
            extra={"target_id": target_id, "run_id": run.id, "error": str(exc)},
        )

    # ---- 目标状态 ----
    target.last_run_at = finished
    target.last_run_status = run.status.value
    db.commit()

    logger.info(
        "inspection run completed",
        extra={
            "target_id": target_id,
            "run_id": run.id,
            "status": run.status.value,
            "critical": run.findings_critical,
            "warn": run.findings_warn,
            "errors": run.error_count,
            "duration_ms": run.duration_ms,
        },
    )
    db.refresh(run)
    return run


def run_inspection_job(target_id: int, trigger_type: str = RunTrigger.SCHEDULE.value,
                       run_id: Optional[int] = None) -> None:
    """调度作业入口：自己开数据库会话，跑完就关。"""
    with SessionLocal() as db:
        try:
            run_inspection(db, target_id, trigger_type, run_id=run_id)
        except Exception as exc:  # noqa: BLE001 —— 作业异常不能让调度器挂掉
            logger.error(
                "scheduled inspection crashed",
                extra={"target_id": target_id, "error": str(exc)},
            )
