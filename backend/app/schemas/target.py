"""巡检目标相关请求/响应模型。"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: 简单的 cron 表达式校验：5 段，每段是 * 或数字或步进/范围
_CRON_FIELD = r"^(\*|\d+|\*/\d+|\d+-\d+(/\d+)?)(,(\*|\d+|\*/\d+|\d+-\d+(/\d+)?))*$"


class TargetIn(BaseModel):
    """新建巡检目标。"""

    name: str = Field(..., min_length=1, max_length=128)
    host: str = Field(..., min_length=1, max_length=255)
    port: int = Field(9419, ge=1, le=65535)
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=256)
    verify_tls: bool = False
    description: Optional[str] = Field(None, max_length=512)
    is_enabled: bool = True
    schedule_cron: Optional[str] = Field(None, max_length=64)
    schedule_timezone: str = "Asia/Shanghai"
    schedule_enabled: bool = False


class TargetUpdateIn(BaseModel):
    """修改巡检目标；password 传了才会更新。"""

    name: Optional[str] = Field(None, min_length=1, max_length=128)
    host: Optional[str] = Field(None, min_length=1, max_length=255)
    port: Optional[int] = Field(None, ge=1, le=65535)
    username: Optional[str] = Field(None, min_length=1, max_length=255)
    password: Optional[str] = Field(None, min_length=1, max_length=256)
    verify_tls: Optional[bool] = None
    description: Optional[str] = Field(None, max_length=512)
    is_enabled: Optional[bool] = None


class ScheduleIn(BaseModel):
    """排期配置。"""

    cron: Optional[str] = Field(None, max_length=64)
    timezone: str = Field("Asia/Shanghai", max_length=64)
    enabled: bool = False

    @field_validator("cron")
    @classmethod
    def _validate_cron(cls, value: Optional[str]) -> Optional[str]:
        """校验 cron 表达式格式（5 段）。"""
        if value is None or value.strip() == "":
            return None
        import re

        fields = value.split()
        if len(fields) != 5:
            raise ValueError("cron 表达式必须是 5 段（分 时 日 月 周）")
        for field in fields:
            if not re.match(_CRON_FIELD, field):
                raise ValueError(f"非法的 cron 字段: {field}")
        return value


class TargetOut(BaseModel):
    """巡检目标输出；**不含口令**，只有 has_password 标志。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    host: str
    port: int
    username: str
    verify_tls: bool
    description: Optional[str] = None
    is_enabled: bool
    has_password: bool = False
    schedule_cron: Optional[str] = None
    schedule_timezone: str = "Asia/Shanghai"
    schedule_enabled: bool = False
    capabilities_checked_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    last_run_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ConnectionTestOut(BaseModel):
    """连通性测试结果。"""

    ok: bool
    server: Optional[dict[str, Any]] = None
    server_time: Optional[str] = None
    iana_tz: Optional[str] = None
    error: Optional[str] = None
