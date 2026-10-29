"""通知渠道接口。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.deps import DbSession, OperatorUser
from app.models.alert import NotificationChannel
from app.notifications.webhook import SIGN_TYPES, TEMPLATES
from app.schemas.alert import ChannelIn, ChannelOut
from app.services import channel_service
from app.utils.errors import NotFoundError, ok

router = APIRouter(prefix="/channels", tags=["通知渠道"])


@router.get("", summary="渠道列表")
def list_channels(db: DbSession, enabled: bool | None = Query(None)) -> dict:
    """列出全部通知渠道。"""
    rows = channel_service.list_channels(db, enabled=enabled)
    return ok({"items": [channel_service.to_out(r) for r in rows], "total": len(rows)})


@router.get("/templates", summary="Webhook 模板与签名方式")
def webhook_templates() -> dict:
    """返回前端可用的 webhook 模板与签名方式。"""
    return ok({"templates": list(TEMPLATES), "sign_types": list(SIGN_TYPES)})


@router.post("", summary="新建渠道")
def create_channel(payload: ChannelIn, db: DbSession,
                   user: OperatorUser) -> dict:
    """新建通知渠道；密钥以密文存储。"""
    row = channel_service.create_channel(
        db,
        name=payload.name,
        channel_type=payload.channel_type,
        enabled=payload.enabled,
        config_json=payload.config,
        secret=payload.secret,
        headers_json=payload.headers,
    )
    return ok(channel_service.to_out(row))


@router.get("/{channel_id}", summary="渠道详情")
def get_channel(channel_id: int, db: DbSession) -> dict:
    """取单个通知渠道。"""
    row = channel_service.get_channel(db, channel_id)
    return ok(channel_service.to_out(row))


@router.put("/{channel_id}", summary="修改渠道")
def update_channel(channel_id: int, payload: ChannelIn, db: DbSession,
                   user: OperatorUser) -> dict:
    """修改通知渠道；secret 传了才会重写密钥。"""
    row = channel_service.get_channel(db, channel_id)
    updated = channel_service.update_channel(
        db,
        row,
        name=payload.name,
        channel_type=payload.channel_type,
        enabled=payload.enabled,
        config_json=payload.config,
        secret=payload.secret,
        headers_json=payload.headers,
    )
    return ok(channel_service.to_out(updated))


@router.delete("/{channel_id}", summary="删除渠道")
def delete_channel(channel_id: int, db: DbSession,
                   user: OperatorUser) -> dict:
    """删除通知渠道。"""
    row = channel_service.get_channel(db, channel_id)
    channel_service.delete_channel(db, row)
    return ok({"message": "渠道已删除"})


@router.post("/{channel_id}/test", summary="测试渠道")
def test_channel(channel_id: int, db: DbSession,
                  user: OperatorUser) -> dict:
    """向该渠道发一条测试消息。"""
    row = channel_service.get_channel(db, channel_id)
    result = channel_service.test_channel(db, row)
    return ok(result)
