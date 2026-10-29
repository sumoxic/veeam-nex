"""巡检运行接口：历史、手动触发、详情。"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.deps import DbSession, OperatorUser
from app.models.finding import Finding
from app.models.inspection import ClockSource, InspectionRun, RunStatus, RunTrigger
from app.schemas.inspection import FindingOut, InspectionRunDetailOut, InspectionRunOut
from app.services import inspection_service, target_service
from app.utils.errors import NotFoundError, ok
from app.utils.timeutil import to_utc_naive, utcnow

router = APIRouter(prefix="/inspections", tags=["巡检运行"])


def _run_out(run: InspectionRun) -> dict:
    data = InspectionRunOut.model_validate(run).model_dump()
    data["status"] = run.status.value
    data["trigger_type"] = run.trigger_type.value
    data["clock_source"] = run.clock_source.value
    return data


@router.get("", summary="运行历史")
def list_inspections(
    db: DbSession,
    target_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
) -> dict:
    """分页查询巡检运行记录。"""
    stmt = select(InspectionRun)
    count_stmt = select(func.count(InspectionRun.id))
    if target_id is not None:
        stmt = stmt.where(InspectionRun.target_id == target_id)
        count_stmt = count_stmt.where(InspectionRun.target_id == target_id)
    if status:
        stmt = stmt.where(InspectionRun.status == status)
        count_stmt = count_stmt.where(InspectionRun.status == status)

    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(InspectionRun.started_at.desc()).offset((page - 1) * size).limit(size)
    ).all()
    return ok({"items": [_run_out(r) for r in rows], "total": total,
               "page": page, "size": size})


@router.post("", summary="立即巡检")
def trigger_inspection(
    db: DbSession,
    user: OperatorUser,
    target_id: int = Query(..., description="巡检目标 id"),
) -> dict:
    """立即对目标执行一次巡检。

    采集耗时较长（目标端点有 200 条/页的上限），因此先建运行记录并立刻返回 run_id，
    实际采集由后台作业完成，客户端不会被超时打断。
    """
    target = target_service.get_target(db, target_id)

    now = to_utc_naive(utcnow())
    run = InspectionRun(
        target_id=target_id,
        trigger_type=RunTrigger.MANUAL,
        status=RunStatus.RUNNING,
        started_at=now,
        clock_source=ClockSource.PLATFORM,
        created_at=now,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    _schedule_manual_run(run.id, target_id)
    return ok({"run_id": run.id, "status": run.status.value,
               "message": f"已排队巡检目标 {target.name}"})


def _schedule_manual_run(run_id: int, target_id: int) -> None:
    """把巡检排成一次性作业；调度器不可用时退回同步执行。"""
    from app.scheduler.bootstrap import get_scheduler

    scheduler = get_scheduler()
    if scheduler is None:
        # 没有调度器（例如单进程调试）就直接在后台线程里跑
        import threading

        from app.services import inspection_service

        threading.Thread(
            target=inspection_service.run_inspection_job,
            args=(target_id, RunTrigger.MANUAL.value, run_id),
            daemon=True,
        ).start()
        return

    from app.scheduler.jobs import inspection_job

    scheduler.add_job(
        inspection_job,
        trigger="date",
        args=[target_id, RunTrigger.MANUAL.value, run_id],
        id=f"manual-inspect:{run_id}",
        replace_existing=True,
        misfire_grace_time=1800,
        name="手动巡检",
    )


@router.get("/{run_id}", summary="运行详情")
def get_inspection(run_id: int, db: DbSession) -> dict:
    """取单次巡检的详情，含原始清单。"""
    run = db.get(InspectionRun, run_id)
    if run is None:
        raise NotFoundError(f"巡检运行记录 {run_id} 不存在")
    data = InspectionRunDetailOut.model_validate(run).model_dump()
    data["status"] = run.status.value
    data["trigger_type"] = run.trigger_type.value
    data["clock_source"] = run.clock_source.value
    return ok(data)


@router.get("/{run_id}/findings", summary="本次运行的发现项")
def run_findings(run_id: int, db: DbSession) -> dict:
    """取该次巡检命中的发现项。"""
    rows = db.scalars(
        select(Finding).where(Finding.last_run_id == run_id).order_by(Finding.id)
    ).all()
    return ok({"items": [FindingOut.model_validate(r).model_dump() for r in rows],
               "total": len(rows)})


@router.get("/{run_id}/inventory", summary="原始清单")
def run_inventory(run_id: int, db: DbSession) -> dict:
    """取该次巡检的原始采集清单。"""
    run = db.get(InspectionRun, run_id)
    if run is None:
        raise NotFoundError(f"巡检运行记录 {run_id} 不存在")
    return ok({"inventory": run.inventory_json or {}})
