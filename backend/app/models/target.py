"""VBR 巡检目标与规则配置。"""
import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Enum,
    ForeignKey,
    Integer,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UTCDateTime


class Target(Base, TimestampMixin):
    """一个 Veeam VBR 实例。"""

    __tablename__ = "targets"
    __table_args__ = (Index("idx_targets_enabled", "is_enabled"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=9419)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    #: Fernet 密文，格式 "fernet:<token>"，任何情况下都不返回给前端
    password_enc: Mapped[str] = mapped_column(String(512), nullable=False)
    #: VBR 默认使用自签名证书，默认不校验
    verify_tls: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ---- 排期（权威数据源，APScheduler 只是它的投影）----
    schedule_cron: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    schedule_timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Asia/Shanghai"
    )
    schedule_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ---- 能力探测缓存（available() 需要 14 次 HTTP 调用，缓存 1 小时）----
    capabilities_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    capabilities_checked_at: Mapped[Optional[datetime]] = mapped_column(
        UTCDateTime, nullable=True
    )

    last_run_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    last_run_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    rule_overrides: Mapped[list["TargetRuleOverride"]] = relationship(
        back_populates="target", cascade="all, delete-orphan"
    )


class RuleSetting(Base, TimestampMixin):
    """全局巡检规则配置（规则目录以 rule_key 为主键）。"""

    __tablename__ = "rule_settings"

    rule_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    #: NULL 表示沿用规则规格里的默认级别
    level: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    params_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class TargetRuleOverride(Base, TimestampMixin):
    """针对单个目标的规则覆盖。

    enabled / level 为 NULL 表示继承全局；params_json 按键覆盖全局参数。
    """

    __tablename__ = "target_rule_overrides"
    __table_args__ = (
        UniqueConstraint("target_id", "rule_key", name="uq_tro_target_rule"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("targets.id", ondelete="CASCADE"), nullable=False
    )
    rule_key: Mapped[str] = mapped_column(
        String(64), ForeignKey("rule_settings.rule_key", ondelete="CASCADE"), nullable=False
    )
    enabled: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    level: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    params_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    target: Mapped[Target] = relationship(back_populates="rule_overrides")


class OperationKind(str, enum.Enum):
    """远程操作类型。"""

    JOB_START = "job.start"
    JOB_RETRY = "job.retry"
    PROXY_ENABLE = "proxy.enable"
    PROXY_DISABLE = "proxy.disable"


class OperationStatus(str, enum.Enum):
    """远程操作状态机。"""

    PENDING = "pending"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXPIRED = "expired"
    REJECTED = "rejected"


class OperationAudit(Base, TimestampMixin):
    """远程操作审计记录。

    建单与执行分两步：创建时只生成确认令牌，不触碰 VBR；
    携带正确令牌调用 confirm 时才真正执行。
    """

    __tablename__ = "operation_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    target_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("targets.id", ondelete="CASCADE"), nullable=False
    )
    operator_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    operation_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    params_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    preview_text: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[OperationStatus] = mapped_column(
        Enum(OperationStatus, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=OperationStatus.PENDING,
    )
    #: HMAC-SHA256(request_id|参数|过期时刻)
    confirmation_token: Mapped[str] = mapped_column(String(64), nullable=False)
    token_expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    vbr_task_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    result_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
