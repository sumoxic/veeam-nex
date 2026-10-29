"""巡检目标接口。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.deps import DbSession, OperatorUser
from app.models.finding import Finding
from app.models.inspection import InspectionRun
from app.schemas.target import (
    ConnectionTestOut,
    ScheduleIn,
    TargetIn,
    TargetOut,
    TargetUpdateIn,
)
from app.services import target_service
from app.utils.errors import ok

router = APIRouter(prefix="/targets", tags=["巡检目标"])


def _to_out(target) -> dict:
    """转成对外结构（不含口令）。"""
    data = TargetOut.model_validate(target).model_dump()
    data["has_password"] = bool(target.password_enc)
    return data


@router.get("", summary="目标列表")
def list_targets(
    db: DbSession,
    enabled: bool | None = Query(None, description="按启用状态过滤"),
    q: str | None = Query(None, description="按名称/地址模糊搜索"),
) -> dict:
    """列出所有 VBR 巡检目标。"""
    targets = target_service.list_targets(db, enabled=enabled, keyword=q)
    return ok({"items": [_to_out(t) for t in targets]})


@router.post("", summary="新建目标")
def create_target(payload: TargetIn, db: DbSession,
                  user: OperatorUser) -> dict:
    """新增一个 VBR 巡检目标；口令加密存储。"""
    target = target_service.create_target(
        db,
        name=payload.name,
        host=payload.host,
        port=payload.port,
        username=payload.username,
        password=payload.password,
        verify_tls=payload.verify_tls,
        description=payload.description,
        is_enabled=payload.is_enabled,
        schedule_cron=payload.schedule_cron,
        schedule_timezone=payload.schedule_timezone,
        schedule_enabled=payload.schedule_enabled and bool(payload.schedule_cron),
    )
    return ok(_to_out(target))


@router.get("/{target_id}", summary="目标详情")
def get_target(target_id: int, db: DbSession) -> dict:
    """取单个目标。"""
    return ok(_to_out(target_service.get_target(db, target_id)))


@router.put("/{target_id}", summary="修改目标")
def update_target(target_id: int, payload: TargetUpdateIn, db: DbSession,
                  user: OperatorUser) -> dict:
    """修改目标；password 传了才会更新口令。"""
    target = target_service.get_target(db, target_id)
    fields = payload.model_dump(exclude_none=True)
    updated = target_service.update_target(db, target, **fields)
    return ok(_to_out(updated))


@router.delete("/{target_id}", summary="删除目标")
def delete_target(target_id: int, db: DbSession,
                  user: OperatorUser) -> dict:
    """删除目标及其运行记录、发现项。"""
    target = target_service.get_target(db, target_id)
    target_service.delete_target(db, target)
    return ok({"message": "目标已删除"})


@router.post("/{target_id}/test-connection", summary="连通性测试")
def test_connection(target_id: int, db: DbSession,
                    user: OperatorUser) -> dict:
    """测试与 VBR 的连通性：登录 + 读服务器信息 + 读服务器时钟。"""
    target = target_service.get_target(db, target_id)
    result = target_service.test_connection(target)
    return ok(ConnectionTestOut(**result).model_dump())


@router.get("/{target_id}/capabilities", summary="能力探测")
def capabilities(target_id: int, db: DbSession, force: bool = Query(False)) -> dict:
    """探测各巡检端点在目标上的可用性（结果缓存 1 小时）。"""
    target = target_service.get_target(db, target_id)
    result = target_service.get_capabilities(db, target, force=force)
    return ok({"items": result, "checked_at": target.capabilities_checked_at})


@router.get("/{target_id}/schedule", summary="排期配置")
def get_schedule(target_id: int, db: DbSession) -> dict:
    """取目标的巡检排期。"""
    target = target_service.get_target(db, target_id)
    return ok(
        {
            "cron": target.schedule_cron,
            "timezone": target.schedule_timezone,
            "enabled": target.schedule_enabled,
        }
    )


@router.put("/{target_id}/schedule", summary="修改排期")
def update_schedule(target_id: int, payload: ScheduleIn, db: DbSession,
                    user: OperatorUser) -> dict:
    """修改巡检排期；保存后调度器会重新注册该目标的作业。"""
    from app.services.scheduler_service import sync_target_schedule

    target = target_service.get_target(db, target_id)
    updated = target_service.update_schedule(
        db, target, payload.cron, payload.timezone, payload.enabled
    )
    sync_target_schedule(updated)
    return ok(
        {
            "cron": updated.schedule_cron,
            "timezone": updated.schedule_timezone,
            "enabled": updated.schedule_enabled,
        }
    )


@router.get("/{target_id}/summary", summary="目标概览")
def target_summary(target_id: int, db: DbSession) -> dict:
    """取目标的关键指标：最近运行、当前未处理发现数。"""
    target = target_service.get_target(db, target_id)

    last_run = db.scalar(
        select(InspectionRun)
        .where(InspectionRun.target_id == target_id)
        .order_by(InspectionRun.started_at.desc())
        .limit(1)
    )
    counts = {}
    for level in ("critical", "warn", "info"):
        counts[level] = db.scalar(
            select(Finding.id).where(
                Finding.target_id == target_id,
                Finding.status != "resolved",
                Finding.level == level,
            ).limit(1)
        )
    counts = {k: (1 if v else 0) for k, v in counts.items()}

    return ok(
        {
            "target": _to_out(target),
            "last_run": {
                "id": last_run.id,
                "status": last_run.status.value,
                "started_at": last_run.started_at,
                "finished_at": last_run.finished_at,
                "findings_critical": last_run.findings_critical,
                "findings_warn": last_run.findings_warn,
            }
            if last_run
            else None,
            "open_findings": counts,
        }
    )
