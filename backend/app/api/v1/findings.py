"""发现项接口：查询、确认、恢复、历史事件。"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.deps import DbSession, OperatorUser
from app.models.finding import FindingEvent
from app.schemas.inspection import BulkAckIn, FindingEventOut, FindingOut
from app.services import finding_service
from app.utils.errors import ok

router = APIRouter(prefix="/findings", tags=["发现项"])


@router.get("", summary="发现项列表")
def list_findings(
    db: DbSession,
    target_id: Optional[int] = Query(None),
    level: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    rule_key: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
) -> dict:
    """分页查询发现项。"""
    rows, total = finding_service.query_findings(
        db,
        target_id=target_id,
        level=level,
        category=category,
        status=status,
        rule_key=rule_key,
        keyword=keyword,
        offset=(page - 1) * size,
        limit=size,
    )
    return ok({"items": [FindingOut.model_validate(r).model_dump() for r in rows],
               "total": total, "page": page, "size": size})


@router.get("/summary", summary="发现项统计")
def findings_summary(db: DbSession, target_id: Optional[int] = Query(None)) -> dict:
    """按级别与状态汇总发现项数量。"""
    return ok(finding_service.summary(db, target_id))


@router.get("/{finding_id}", summary="发现项详情")
def get_finding(finding_id: int, db: DbSession) -> dict:
    """取单条发现项。"""
    row = finding_service.get_finding(db, finding_id)
    return ok(FindingOut.model_validate(row).model_dump())


@router.get("/{finding_id}/events", summary="发现项历史")
def finding_events(finding_id: int, db: DbSession, limit: int = Query(100, ge=1, le=500)) -> dict:
    """取该发现项的历史事件（出现/持续/恢复过程）。"""
    rows = db.scalars(
        select(FindingEvent)
        .where(FindingEvent.finding_id == finding_id)
        .order_by(FindingEvent.created_at.desc())
        .limit(limit)
    ).all()
    return ok({"items": [FindingEventOut.model_validate(r).model_dump() for r in rows],
               "total": len(rows)})


@router.post("/{finding_id}/ack", summary="确认发现项")
def acknowledge(finding_id: int, db: DbSession,
                 user: OperatorUser) -> dict:
    """标记为已知悉。"""
    row = finding_service.get_finding(db, finding_id)
    updated = finding_service.acknowledge(db, row, user.id)
    return ok(FindingOut.model_validate(updated).model_dump())


@router.post("/{finding_id}/resolve", summary="标记已恢复")
def resolve(finding_id: int, db: DbSession,
            user: OperatorUser) -> dict:
    """手动标记为已恢复。"""
    row = finding_service.get_finding(db, finding_id)
    updated = finding_service.resolve(db, row)
    return ok(FindingOut.model_validate(updated).model_dump())


@router.post("/bulk-ack", summary="批量确认")
def bulk_ack(payload: BulkAckIn, db: DbSession,
             user: OperatorUser) -> dict:
    """批量确认发现项；传 finding_ids 则只处理指定条目，否则按目标处理全部未确认项。"""
    count = finding_service.bulk_acknowledge(
        db, user.id, payload.finding_ids, payload.target_id
    )
    return ok({"acknowledged": count})
