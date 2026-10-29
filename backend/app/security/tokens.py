"""JWT 令牌签发与校验。

访问令牌：短有效期（默认 30 分钟），HS256。
刷新令牌：长有效期（默认 7 天），**只以哈希形式入库**，每次使用后轮换。
"""
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt

from app.config import get_settings

#: 令牌类型声明
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


class TokenError(Exception):
    """令牌无效或过期。"""


def _secret() -> str:
    settings = get_settings()
    if not settings.jwt_secret_key:
        raise TokenError("未配置 JWT_SECRET_KEY")
    return settings.jwt_secret_key


def _encode(payload: dict) -> str:
    settings = get_settings()
    return jwt.encode(payload, _secret(), algorithm=settings.jwt_algorithm)


def create_access_token(user_id: int, username: str, role: str) -> tuple[str, int]:
    """签发访问令牌，返回 (令牌, 有效期秒数)。"""
    settings = get_settings()
    ttl = settings.access_token_expire_minutes * 60
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "type": TOKEN_TYPE_ACCESS,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl)).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return _encode(payload), ttl


def create_refresh_token(user_id: int) -> tuple[str, datetime]:
    """签发刷新令牌，返回 (令牌明文, 过期时刻)。"""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=settings.refresh_token_expire_days)
    payload = {
        "sub": str(user_id),
        "type": TOKEN_TYPE_REFRESH,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return _encode(payload), expires_at


def decode_token(token: str, expected_type: str = TOKEN_TYPE_ACCESS) -> dict[str, Any]:
    """校验并解析令牌。"""
    settings = get_settings()
    try:
        payload = jwt.decode(token, _secret(), algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("令牌已过期") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError(f"令牌无效: {exc}") from exc
    if payload.get("type") != expected_type:
        raise TokenError(f"令牌类型错误，期望 {expected_type}")
    return payload


def hash_refresh_token(token: str) -> str:
    """刷新令牌入库前先哈希，只存哈希值。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def revoke_token_signature(user_id: int) -> str:
    """生成操作确认令牌用的 HMAC 签名。"""
    import hmac

    settings = get_settings()
    return hmac.new(
        _secret().encode("utf-8"),
        str(user_id).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
