"""审计接口（仅管理员）。

远程操作的完整生命周期都记录在 operation_audit 表里，
这里提供管理员视角的查询与汇总。
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.deps import DbSession, require_admin
from app.models.target import OperationAudit, OperationStatus
from app.services import operation_service
from app.utils.errors import ok

router = APIRouter(prefix="/audit", tags=["审计"], dependencies=[Depends(require_admin)])


@router.get("/operations", summary="操作审计明细")
def audit_operations(
    db: DbSession,
    target_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    kind: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
) -> dict:
    """分页查询全部操作审计记录。"""
    rows, total = operation_service.list_operations(
        db, target_id, status, kind, (page - 1) * size, size
    )
    items = [
        {
            "request_id": r.request_id,
            "target_id": r.target_id,
            "operator_id": r.operator_id,
            "operation_kind": r.operation_kind,
            "params": dict(r.params_json or {}),
            "preview_text": r.preview_text,
            "status": r.status.value,
            "confirmed_at": r.confirmed_at,
            "vbr_task_id": r.vbr_task_id,
            "error_message": r.error_message,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        }
        for r in rows
    ]
    return ok({"items": items, "total": total, "page": page, "size": size})


@router.get("/summary", summary="审计汇总")
def audit_summary(db: DbSession) -> dict:
    """按状态与操作类型汇总审计记录。"""
    by_status = db.execute(
        select(OperationAudit.status, func.count(OperationAudit.id)).group_by(
            OperationAudit.status
        )
    ).all()
    by_kind = db.execute(
        select(OperationAudit.operation_kind, func.count(OperationAudit.id)).group_by(
            OperationAudit.operation_kind
        )
    ).all()
    return ok(
        {
            "by_status": {status.value: count for status, count in by_status},
            "by_kind": {kind: count for kind, count in by_kind},
            "pending": db.scalar(
                select(func.count(OperationAudit.id)).where(
                    OperationAudit.status == OperationStatus.PENDING
                )
            )
            or 0,
        }
    )
