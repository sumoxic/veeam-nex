"""告警事件接口：查询与重试。"""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.deps import DbSession, OperatorUser
from app.models.alert import AlertEvent
from app.schemas.alert import AlertEventOut
from app.services import alert_service
from app.utils.errors import NotFoundError, ok

router = APIRouter(prefix="/alert-events", tags=["告警事件"])


@router.get("", summary="告警事件列表")
def list_events(
    db: DbSession,
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    target_id: Optional[int] = Query(None),
    alert_rule_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
) -> dict:
    """分页查询告警事件（含被去重/冷却拦下的 suppressed 记录）。"""
    rows, total = alert_service.list_events(
        db,
        status=status,
        severity=severity,
        target_id=target_id,
        alert_rule_id=alert_rule_id,
        offset=(page - 1) * size,
        limit=size,
    )
    return ok({"items": [AlertEventOut.model_validate(r).model_dump() for r in rows],
               "total": total, "page": page, "size": size})


@router.get("/{event_id}", summary="告警事件详情")
def get_event(event_id: int, db: DbSession) -> dict:
    """取单条告警事件。"""
    row = db.get(AlertEvent, event_id)
    if row is None:
        raise NotFoundError(f"告警事件 {event_id} 不存在")
    return ok(AlertEventOut.model_validate(row).model_dump())


@router.post("/{event_id}/retry", summary="重试投递")
def retry_event(event_id: int, db: DbSession,
                user: OperatorUser) -> dict:
    """手动重试一条失败或被抑制的告警事件。"""
    from app.notifications import dispatcher

    row = db.get(AlertEvent, event_id)
    if row is None:
        raise NotFoundError(f"告警事件 {event_id} 不存在")
    ok_sent = dispatcher.retry_event(db, row)
    db.refresh(row)
    return ok({"sent": ok_sent, "event": AlertEventOut.model_validate(row).model_dump()})
