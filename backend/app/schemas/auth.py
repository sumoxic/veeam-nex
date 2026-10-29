"""认证相关请求/响应模型。"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class LoginIn(BaseModel):
    """登录请求。"""

    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=256)


class TokenOut(BaseModel):
    """登录/刷新返回的令牌。"""

    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int = 0


class UserOut(BaseModel):
    """用户信息（不含口令哈希）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    role: str
    is_active: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime


class UserCreateIn(BaseModel):
    """新建用户。"""

    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=8, max_length=256)
    email: Optional[str] = Field(None, max_length=255)
    display_name: Optional[str] = Field(None, max_length=128)
    role: str = "viewer"


class UserUpdateIn(BaseModel):
    """修改用户。"""

    email: Optional[str] = Field(None, max_length=255)
    display_name: Optional[str] = Field(None, max_length=128)
    role: Optional[str] = None
    is_active: Optional[bool] = None


class PasswordChangeIn(BaseModel):
    """修改自己的口令。"""

    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=256)


class PasswordResetIn(BaseModel):
    """管理员重置他人口令。"""

    new_password: str = Field(..., min_length=8, max_length=256)
