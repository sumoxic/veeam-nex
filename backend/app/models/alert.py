"""告警规则、通知渠道与告警事件。"""
import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UTCDateTime


class ChannelType(str, enum.Enum):
    """通知渠道类型。"""

    SMTP = "smtp"
    WEBHOOK = "webhook"


class AlertRule(Base, TimestampMixin):
    """告警规则。

    匹配条件：rule_key（精确）或 category（整类），再叠加目标白名单与最小级别。
    路由：channel_routes 形如 [{"channel_id": 1, "min_level": "critical"}]，
    同一规则可以把不同级别分发给不同渠道。
    """

    __tablename__ = "alert_rules"
    __table_args__ = (Index("idx_ar_enabled", "enabled"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    match_rule_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    match_category: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    #: NULL 或空数组表示匹配所有目标
    match_target_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    min_level: Mapped[str] = mapped_column(String(16), nullable=False, default="warn")
    channel_routes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    dedup_window_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    notify_on_resolve: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class NotificationChannel(Base, TimestampMixin):
    """通知渠道配置。

    secret_enc 保存 SMTP 口令或 Webhook 签名密钥，永不返回给前端。
    """

    __tablename__ = "notification_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    channel_type: Mapped[ChannelType] = mapped_column(
        Enum(ChannelType, values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    secret_enc: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    headers_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    last_test_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    last_test_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)


class AlertEventStatus(str, enum.Enum):
    """告警事件投递状态。

    suppressed —— 被去重窗口或冷却期拦下，仍然落库以便运维看到「为什么没发」
    """

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    SUPPRESSED = "suppressed"


class AlertEventType(str, enum.Enum):
    """告警事件类型。"""

    RAISED = "raised"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class AlertEvent(Base):
    """一条告警事件的投递记录。"""

    __tablename__ = "alert_events"
    __table_args__ = (
        Index("idx_ae_dedup", "dedup_key", "created_at"),
        Index("idx_ae_status", "status"),
        Index("idx_ae_target", "target_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_rule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("notification_channels.id", ondelete="CASCADE"), nullable=False
    )
    target_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("targets.id", ondelete="CASCADE"), nullable=True
    )
    finding_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("findings.id", ondelete="CASCADE"), nullable=True
    )
    run_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("inspection_runs.id", ondelete="CASCADE"), nullable=True
    )
    fingerprint: Mapped[str] = mapped_column(String(40), nullable=False)
    dedup_key: Mapped[str] = mapped_column(String(40), nullable=False)
    event_type: Mapped[AlertEventType] = mapped_column(
        Enum(AlertEventType, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=AlertEventType.RAISED,
    )
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[AlertEventStatus] = mapped_column(
        Enum(AlertEventStatus, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=AlertEventStatus.PENDING,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
