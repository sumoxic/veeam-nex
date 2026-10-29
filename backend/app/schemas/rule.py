"""规则目录与规则配置的请求/响应模型。"""
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class RuleCatalogueOut(BaseModel):
    """规则目录条目。"""

    model_config = ConfigDict(from_attributes=True)

    rule_key: str
    category: str
    title: str
    description: str
    default_level: str
    collection: Optional[str] = None
    default_params: dict = Field(default_factory=dict)
    param_schema: list = Field(default_factory=list)


class RuleSettingOut(BaseModel):
    """规则的全局配置。"""

    model_config = ConfigDict(from_attributes=True)

    rule_key: str
    enabled: bool
    level: Optional[str] = None
    params_json: dict = Field(default_factory=dict)
    description: Optional[str] = None
    updated_by: Optional[int] = None


class RuleConfigIn(BaseModel):
    """设置规则的启用状态、级别与阈值参数。"""

    enabled: Optional[bool] = None
    level: Optional[str] = Field(None, description="留空表示沿用规则默认级别")
    params: Optional[dict] = Field(None, description="阈值参数，按键覆盖全局值")


class RuleOverrideOut(RuleSettingOut):
    """目标的规则覆盖。"""

    target_id: int = 0
