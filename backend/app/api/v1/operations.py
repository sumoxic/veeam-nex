"""远程操作接口：建单 → 确认 / 拒绝。"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.deps import DbSession, OperatorUser
from app.services import operation_service
from app.utils.errors import ok

router = APIRouter(prefix="/operations", tags=["远程操作"])


class OperationIn(BaseModel):
    """建单请求。"""

    target_id: int
    kind: str = Field(..., description="job.start / job.retry / proxy.enable / proxy.disable")
    params: dict = Field(default_factory=dict)


class ConfirmIn(BaseModel):
    """确认请求。"""

    token: str = Field(..., description="建单时返回的确认令牌")


def _out(row) -> dict:
    return {
        "request_id": row.request_id,
        "id": row.id,
        "target_id": row.target_id,
        "operator_id": row.operator_id,
        "operation_kind": row.operation_kind,
        "params": dict(row.params_json or {}),
        "preview_text": row.preview_text,
        "status": row.status.value,
        "token_expires_at": row.token_expires_at,
        "confirmed_at": row.confirmed_at,
        "vbr_task_id": row.vbr_task_id,
        "result": row.result_json,
        "error_message": row.error_message,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


@router.get("/kinds", summary="可用的操作类型")
def list_kinds() -> dict:
    """返回支持的远程操作类型清单。"""
    items = operation_service.operation_kinds()
    return ok({"items": items, "total": len(items)})


@router.get("", summary="操作审计列表")
def list_operations(
    db: DbSession,
    target_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    kind: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
) -> dict:
    """分页查询远程操作审计记录。"""
    rows, total = operation_service.list_operations(
        db, target_id, status, kind, (page - 1) * size, size
    )
    return ok({"items": [_out(r) for r in rows], "total": total, "page": page, "size": size})


@router.post("", summary="创建操作单")
def create_operation(payload: OperationIn, db: DbSession, user: OperatorUser) -> dict:
    """建单并返回确认令牌。

    此处 **不会** 调用 VBR，只有携带令牌调用 confirm 才会真正执行。
    """
    row = operation_service.create_operation(
        db, payload.target_id, payload.kind, payload.params, user.id
    )
    return ok(
        {
            **_out(row),
            "confirmation_token": row.confirmation_token,
            "message": "操作单已创建，请确认后执行",
        }
    )


@router.get("/{request_id}", summary="操作单详情")
def get_operation(request_id: str, db: DbSession) -> dict:
    """取单个操作单。"""
    row = operation_service.get_operation(db, request_id)
    return ok(_out(row))


@router.post("/{request_id}/confirm", summary="确认并执行")
def confirm_operation(request_id: str, payload: ConfirmIn, db: DbSession,
                      user: OperatorUser) -> dict:
    """携带正确令牌执行操作；令牌错误或过期则拒绝且不改变状态。"""
    row = operation_service.get_operation(db, request_id)
    updated = operation_service.confirm_operation(db, row, payload.token)
    return ok(_out(updated))


@router.post("/{request_id}/reject", summary="拒绝操作")
def reject_operation(request_id: str, db: DbSession, user: OperatorUser) -> dict:
    """拒绝尚未执行的操作单。"""
    row = operation_service.get_operation(db, request_id)
    updated = operation_service.reject_operation(db, row)
    return ok(_out(updated))
