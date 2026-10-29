"""巡检运行与发现项的请求/响应模型。"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class InspectionRunOut(BaseModel):
    """巡检运行记录。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    target_id: int
    trigger_type: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    clock_source: str
    vbr_server_time: Optional[datetime] = None
    vbr_build: Optional[str] = None
    findings_total: int = 0
    findings_critical: int = 0
    findings_warn: int = 0
    findings_info: int = 0
    error_count: int = 0
    error_message: Optional[str] = None
    created_at: datetime


class InspectionRunDetailOut(InspectionRunOut):
    """运行详情：附带原始清单。"""

    inventory_json: Optional[dict] = None


class InspectionRunIn(BaseModel):
    """手动触发巡检。"""

    target_id: int = Field(..., description="巡检目标 id")
    trigger_type: str = Field("manual", description="触发来源标记")


class FindingOut(BaseModel):
    """发现项。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    target_id: int
    fingerprint: str
    rule_key: str
    category: str
    level: str
    subject: str
    subject_key: str
    message: str
    metric_value: Optional[float] = None
    threshold_value: Optional[float] = None
    status: str
    occurrences: int = 0
    first_seen_at: datetime
    last_seen_at: datetime
    last_run_id: Optional[int] = None
    resolved_at: Optional[datetime] = None
    acknowledged_by: Optional[int] = None
    acknowledged_at: Optional[datetime] = None


class FindingEventOut(BaseModel):
    """发现项历史事件。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    finding_id: int
    run_id: int
    fingerprint: str
    level: str
    message: Optional[str] = None
    created_at: datetime


class BulkAckIn(BaseModel):
    """批量确认。"""

    finding_ids: Optional[list[int]] = None
    target_id: Optional[int] = None
