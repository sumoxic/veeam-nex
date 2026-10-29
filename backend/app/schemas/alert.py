"""告警规则、通知渠道、告警事件的请求/响应模型。"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ChannelRoute(BaseModel):
    """一条路由：指定渠道与该渠道的级别门槛。"""

    channel_id: int
    min_level: str = Field("warn", description="critical / warn / info")


class AlertRuleIn(BaseModel):
    """新建/修改告警规则。"""

    name: str = Field(..., min_length=1, max_length=128)
    enabled: bool = True
    match_rule_key: Optional[str] = Field(None, max_length=64)
    match_category: Optional[str] = Field(None, max_length=32)
    match_target_ids: Optional[list[int]] = None
    min_level: str = "warn"
    channel_routes: list[ChannelRoute] = Field(default_factory=list)
    cooldown_minutes: int = Field(60, ge=0, le=10080)
    dedup_window_hours: int = Field(24, ge=1, le=8760)
    notify_on_resolve: bool = False


class AlertRuleOut(AlertRuleIn):
    """告警规则。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class ChannelIn(BaseModel):
    """新建/修改通知渠道。"""

    name: str = Field(..., min_length=1, max_length=128)
    channel_type: str = Field(..., description="smtp / webhook")
    enabled: bool = True
    config: dict = Field(default_factory=dict)
    secret: Optional[str] = Field(None, description="SMTP 口令或 Webhook 签名密钥")
    headers: Optional[dict] = None


class ChannelOut(BaseModel):
    """通知渠道（不含密钥）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    channel_type: str
    enabled: bool
    config: dict = Field(default_factory=dict)
    headers: dict = Field(default_factory=dict)
    has_secret: bool = False
    last_test_at: Optional[datetime] = None
    last_test_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AlertEventOut(BaseModel):
    """告警事件。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_rule_id: int
    channel_id: int
    target_id: Optional[int] = None
    finding_id: Optional[int] = None
    run_id: Optional[int] = None
    fingerprint: str
    dedup_key: str
    event_type: str
    severity: str
    title: Optional[str] = None
    body: Optional[str] = None
    status: str
    attempts: int = 0
    error_message: Optional[str] = None
    sent_at: Optional[datetime] = None
    created_at: datetime
