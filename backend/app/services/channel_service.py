"""通知渠道服务：增删改查、发送器构造、测试发送。"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.alert import ChannelType, NotificationChannel
from app.notifications.base import Message, Notifier, NotifyError
from app.notifications.smtp import SmtpNotifier
from app.notifications.webhook import WebhookNotifier
from app.security.crypto import decrypt, encrypt
from app.utils.errors import ConflictError, NotFoundError
from app.utils.timeutil import to_utc_naive, utcnow


def list_channels(db: Session, enabled: Optional[bool] = None) -> list[NotificationChannel]:
    """列出所有通知渠道。"""
    stmt = select(NotificationChannel)
    if enabled is not None:
        stmt = stmt.where(NotificationChannel.enabled == enabled)
    return list(db.scalars(stmt.order_by(NotificationChannel.id)).all())


def get_channel(db: Session, channel_id: int) -> NotificationChannel:
    """取单个渠道，不存在抛 404。"""
    row = db.get(NotificationChannel, channel_id)
    if row is None:
        raise NotFoundError(f"通知渠道 {channel_id} 不存在")
    return row


def create_channel(db: Session, **fields) -> NotificationChannel:
    """新建渠道；口令以密文存储。"""
    existing = db.scalar(
        select(NotificationChannel).where(NotificationChannel.name == fields["name"])
    )
    if existing is not None:
        raise ConflictError(f"渠道名称 {fields['name']} 已存在")

    secret = fields.pop("secret", None)
    channel_type = fields.pop("channel_type")
    if not isinstance(channel_type, ChannelType):
        channel_type = ChannelType(channel_type)

    channel = NotificationChannel(
        channel_type=channel_type,
        secret_enc=encrypt(secret) if secret else None,
        **fields,
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel


def update_channel(db: Session, channel: NotificationChannel, **fields) -> NotificationChannel:
    """更新渠道；secret 传了才会重写密文。"""
    secret = fields.pop("secret", None)
    if secret:
        channel.secret_enc = encrypt(secret)
    if "channel_type" in fields and fields["channel_type"]:
        value = fields["channel_type"]
        channel.channel_type = value if isinstance(value, ChannelType) else ChannelType(value)
    for key, value in fields.items():
        if value is not None:
            setattr(channel, key, value)
    db.commit()
    db.refresh(channel)
    return channel


def delete_channel(db: Session, channel: NotificationChannel) -> None:
    """删除渠道（其下的告警事件随外键级联清理）。"""
    db.delete(channel)
    db.commit()


def build_notifier(channel: NotificationChannel) -> Notifier:
    """按渠道类型构造发送器（在此解密密钥）。"""
    secret = decrypt(channel.secret_enc) if channel.secret_enc else None
    config = dict(channel.config_json or {})
    if channel.channel_type == ChannelType.SMTP:
        return SmtpNotifier(config, secret)
    return WebhookNotifier(config, secret, channel.headers_json)


def test_channel(db: Session, channel: NotificationChannel) -> dict:
    """发送一条测试消息，记录结果。"""
    message = Message(
        title="Veeam 巡检平台通道测试",
        body="这是一条来自 Veeam 巡检平台的测试通知，收到即表示渠道配置正确。",
        severity="info",
    )
    now = to_utc_naive(utcnow())
    try:
        build_notifier(channel).send(message)
    except NotifyError as exc:
        channel.last_test_at = now
        channel.last_test_status = f"failed: {exc}"[:255]
        db.commit()
        return {"ok": False, "error": str(exc)}

    channel.last_test_at = now
    channel.last_test_status = "ok"
    db.commit()
    return {"ok": True, "error": None}


def to_out(channel: NotificationChannel) -> dict:
    """对外结构：不含密钥，只暴露是否存在。"""
    return {
        "id": channel.id,
        "name": channel.name,
        "channel_type": channel.channel_type.value,
        "enabled": channel.enabled,
        "config": dict(channel.config_json or {}),
        "headers": dict(channel.headers_json or {}),
        "has_secret": bool(channel.secret_enc),
        "last_test_at": channel.last_test_at,
        "last_test_status": channel.last_test_status,
        "created_at": channel.created_at,
        "updated_at": channel.updated_at,
    }
