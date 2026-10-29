"""指标与仪表盘接口。"""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.deps import DbSession
from app.services import metrics_service
from app.utils.errors import ok

router = APIRouter(tags=["指标"])


@router.get("/dashboard/summary", summary="仪表盘汇总")
def dashboard_summary(db: DbSession, target_id: Optional[int] = Query(None)) -> dict:
    """目标健康卡、发现项分布与许可用量。"""
    return ok(metrics_service.dashboard_summary(db, target_id))


@router.get("/dashboard/runs", summary="近期巡检轮次")
def dashboard_runs(
    db: DbSession, limit: int = Query(40, ge=1, le=200)
) -> dict:
    """供仪表盘按巡检时间筛选的近期轮次列表。"""
    items = metrics_service.recent_runs(db, limit)
    return ok({"items": items, "total": len(items)})


@router.get("/dashboard/runs/{run_id}", summary="单轮巡检仪表盘")
def dashboard_run(run_id: int, db: DbSession) -> dict:
    """按指定轮次展示当时 VBR 的任务、存储库、还原点与发现项。"""
    return ok(metrics_service.run_dashboard(db, run_id))


@router.get("/metrics/repository-free-space", summary="仓库剩余空间趋势")
def repository_free_space(
    db: DbSession,
    target_id: int = Query(...),
    repository_id: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
) -> dict:
    """仓库剩余空间百分比趋势序列。"""
    items = metrics_service.repository_free_space_trend(
        db, target_id, repository_id, days
    )
    return ok({"items": items, "total": len(items)})


@router.get("/metrics/job-last-run", summary="作业上次运行趋势")
def job_last_run(
    db: DbSession,
    target_id: int = Query(...),
    job_id: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
) -> dict:
    """作业上次运行时间趋势序列。"""
    items = metrics_service.job_last_success_trend(db, target_id, job_id, days)
    return ok({"items": items, "total": len(items)})


@router.get("/metrics/restore-point-age", summary="还原点时效趋势")
def restore_point_age(
    db: DbSession,
    target_id: int = Query(...),
    object_name: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
) -> dict:
    """还原点时效（小时）趋势序列。"""
    items = metrics_service.restore_point_age_trend(db, target_id, object_name, days)
    return ok({"items": items, "total": len(items)})


@router.get("/metrics/findings-trend", summary="发现项趋势")
def findings_trend(
    db: DbSession,
    target_id: Optional[int] = Query(None),
    days: int = Query(30, ge=1, le=365),
) -> dict:
    """按级别统计的发现项数量趋势。"""
    items = metrics_service.findings_trend(db, target_id, days)
    return ok({"items": items, "total": len(items)})
