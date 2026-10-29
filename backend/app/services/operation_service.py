"""远程操作服务：两步确认 + 审计。

安全模型：
- `create` 只建单并生成确认令牌，**绝不调用 VBR**；
- `confirm` 校验 HMAC 令牌与有效期后才真正执行；
- 每一步都留审计记录（operation_audit）。
"""
import hashlib
import hmac
import json
import uuid
from datetime import timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.logging import logger
from app.models.target import OperationAudit, OperationStatus
from app.utils.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.utils.timeutil import to_utc_naive, utcnow
from app.vbr.exceptions import VbrError
from app.vbr.operations import OPERATION_SPECS, get_spec

#: 确认令牌有效期（分钟）
TOKEN_TTL_MINUTES = 15


def _canonical(params: dict) -> str:
    """参数的规范表示，保证同样参数生成同样令牌。"""
    return json.dumps(params, sort_keys=True, ensure_ascii=False, default=str)


def _sign(request_id: str, params: dict, expires_at) -> str:
    """生成确认令牌：HMAC-SHA256(密钥, request_id|参数|过期时刻)。"""
    payload = f"{request_id}|{_canonical(params)}|{expires_at.isoformat()}"
    key = get_settings().jwt_secret_key.encode("utf-8")
    return hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def build_preview(kind: str, params: dict, target_name: str) -> str:
    """生成人类可读的预览文本，确认前给操作员看。"""
    spec = get_spec(kind)
    description = spec.description if spec else kind
    entity_id = params.get(spec.id_param) if spec else ""
    detail = "，".join(f"{k}={v}" for k, v in sorted(params.items()))
    return f"对目标「{target_name}」执行：{description}（{detail}），实体 {entity_id}"


def create_operation(
    db: Session,
    target_id: int,
    kind: str,
    params: dict,
    operator_id: Optional[int] = None,
) -> OperationAudit:
    """建单：生成确认令牌，不调用 VBR。"""
    spec = get_spec(kind)
    if spec is None:
        raise ValidationError(f"不支持的操作类型: {kind}")

    params = dict(params or {})
    try:
        spec.validate(params)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    from app.models.target import Target

    target = db.get(Target, target_id)
    if target is None:
        raise NotFoundError(f"巡检目标 {target_id} 不存在")

    now = to_utc_naive(utcnow())
    expires_at = now + timedelta(minutes=TOKEN_TTL_MINUTES)
    request_id = str(uuid.uuid4())
    preview = build_preview(kind, params, target.name)

    row = OperationAudit(
        request_id=request_id,
        target_id=target_id,
        operator_id=operator_id,
        operation_kind=kind,
        params_json=params,
        preview_text=preview[:512],
        status=OperationStatus.PENDING,
        confirmation_token=_sign(request_id, params, expires_at),
        token_expires_at=expires_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info(
        "operation created",
        extra={"request_id": request_id, "target_id": target_id, "kind": kind},
    )
    return row


def get_operation(db: Session, request_id: str) -> OperationAudit:
    """按 request_id 取操作单。"""
    row = db.scalar(select(OperationAudit).where(OperationAudit.request_id == request_id))
    if row is None:
        raise NotFoundError(f"操作单 {request_id} 不存在")
    return row


def confirm_operation(
    db: Session,
    row: OperationAudit,
    token: str,
) -> OperationAudit:
    """确认并执行：校验令牌 → 调 VBR → 记录结果。"""
    if row.status != OperationStatus.PENDING:
        raise ConflictError(f"操作单当前状态为 {row.status.value}，不能确认")

    now = to_utc_naive(utcnow())
    if row.token_expires_at < now:
        row.status = OperationStatus.EXPIRED
        db.commit()
        raise ForbiddenError("确认令牌已过期，请重新建单")

    expected = _sign(row.request_id, row.params_json, row.token_expires_at)
    if not hmac.compare_digest(expected, token or ""):
        logger.warning(
            "operation confirmation token mismatch",
            extra={"request_id": row.request_id, "target_id": row.target_id},
        )
        raise ForbiddenError("确认令牌不正确")

    row.status = OperationStatus.EXECUTING
    row.confirmed_at = now
    db.commit()

    spec = get_spec(row.operation_kind)
    try:
        from app.services import target_service

        target = target_service.get_target(db, row.target_id)
        client = target_service.build_client(target)
        entity_id = row.params_json.get(spec.id_param)
        path = spec.path_builder(entity_id)
        body = spec.body_builder(row.params_json) if spec.body_builder else None
        result = client.post(path, body=body)
    except VbrError as exc:
        row.status = OperationStatus.FAILED
        row.error_message = str(exc)[:2000]
        db.commit()
        logger.error(
            "operation failed",
            extra={"request_id": row.request_id, "target_id": row.target_id, "error": str(exc)},
        )
        raise ConflictError(f"远程操作执行失败: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 —— 客户端异常也要把单据落到失败态
        row.status = OperationStatus.FAILED
        row.error_message = str(exc)[:2000]
        db.commit()
        logger.error(
            "operation crashed",
            extra={"request_id": row.request_id, "target_id": row.target_id, "error": str(exc)},
        )
        raise ConflictError(f"远程操作执行失败: {exc}") from exc

    row.status = OperationStatus.SUCCEEDED
    row.result_json = result if isinstance(result, dict) else {"response": result}
    if isinstance(row.result_json, dict):
        task_id = row.result_json.get("taskId") or row.result_json.get("id")
        if task_id:
            row.vbr_task_id = str(task_id)
    db.commit()
    db.refresh(row)
    logger.info(
        "operation succeeded",
        extra={
            "request_id": row.request_id,
            "target_id": row.target_id,
            "kind": row.operation_kind,
            "vbr_task_id": row.vbr_task_id,
        },
    )
    return row


def reject_operation(db: Session, row: OperationAudit) -> OperationAudit:
    """拒绝执行。"""
    if row.status != OperationStatus.PENDING:
        raise ConflictError(f"操作单当前状态为 {row.status.value}，不能拒绝")
    row.status = OperationStatus.REJECTED
    db.commit()
    db.refresh(row)
    logger.info(
        "operation rejected", extra={"request_id": row.request_id, "target_id": row.target_id}
    )
    return row


def list_operations(
    db: Session,
    target_id: Optional[int] = None,
    status: Optional[str] = None,
    kind: Optional[str] = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[OperationAudit], int]:
    """分页查询操作审计记录。"""
    from sqlalchemy import func

    stmt = select(OperationAudit)
    count_stmt = select(func.count(OperationAudit.id))
    if target_id is not None:
        stmt = stmt.where(OperationAudit.target_id == target_id)
        count_stmt = count_stmt.where(OperationAudit.target_id == target_id)
    if status:
        stmt = stmt.where(OperationAudit.status == status)
        count_stmt = count_stmt.where(OperationAudit.status == status)
    if kind:
        stmt = stmt.where(OperationAudit.operation_kind == kind)
        count_stmt = count_stmt.where(OperationAudit.operation_kind == kind)

    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(OperationAudit.created_at.desc()).offset(offset).limit(limit)
    ).all()
    return list(rows), total


def operation_kinds() -> list[dict]:
    """可用的操作类型清单（给前端渲染表单用）。"""
    return [
        {
            "kind": spec.kind,
            "description": spec.description,
            "id_param": spec.id_param,
        }
        for spec in OPERATION_SPECS.values()
    ]
