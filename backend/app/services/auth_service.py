"""认证服务：登录、令牌签发与轮换、口令修改。"""
import hashlib
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import RefreshToken, User, UserRole
from app.security.passwords import hash_password, password_strength_error, verify_password
from app.security.tokens import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_refresh_token,
)
from app.utils.errors import BadRequestError, ConflictError, UnauthorizedError
from app.utils.timeutil import to_utc_naive

#: 刷新令牌 cookie 名
COOKIE_ACCESS = "vi_token"
COOKIE_REFRESH = "vi_refresh"


def authenticate(db: Session, username: str, password: str) -> User:
    """校验账号口令，返回用户。"""
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not verify_password(password, user.password_hash):
        raise UnauthorizedError("用户名或口令不正确")
    if not user.is_active:
        raise UnauthorizedError("账号已被停用")
    return user


def issue_tokens(db: Session, user: User) -> dict:
    """签发访问令牌与刷新令牌，并把刷新令牌哈希入库。"""
    access_token, expires_in = create_access_token(
        user.id, user.username, user.role.value
    )
    refresh_token, refresh_expires = create_refresh_token(user.id)

    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=to_utc_naive(refresh_expires),
            created_at=to_utc_naive(datetime.now(timezone.utc)),
        )
    )
    user.last_login_at = to_utc_naive(datetime.now(timezone.utc))
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": expires_in,
        "token_type": "bearer",
    }


def rotate_refresh_token(db: Session, refresh_token: str) -> tuple[User, dict]:
    """校验刷新令牌并轮换（旧的立即作废）。"""
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except TokenError as exc:
        raise UnauthorizedError(str(exc)) from exc

    token_hash = hash_refresh_token(refresh_token)
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    if row is None or row.revoked_at is not None:
        raise UnauthorizedError("刷新令牌无效")
    if row.expires_at < to_utc_naive(datetime.now(timezone.utc)):
        raise UnauthorizedError("刷新令牌已过期")

    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("账号不可用")

    row.revoked_at = to_utc_naive(datetime.now(timezone.utc))
    db.flush()
    tokens = issue_tokens(db, user)
    return user, tokens


def revoke_refresh_token(db: Session, refresh_token: str) -> None:
    """作废一个刷新令牌（登出）。"""
    token_hash = hash_refresh_token(refresh_token)
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    if row is not None and row.revoked_at is None:
        row.revoked_at = to_utc_naive(datetime.now(timezone.utc))
        db.commit()


def revoke_all_tokens(db: Session, user_id: int) -> None:
    """作废某用户的全部刷新令牌（改密、停用账号时调用）。"""
    rows = db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        )
    ).all()
    now = to_utc_naive(datetime.now(timezone.utc))
    for row in rows:
        row.revoked_at = now
    db.commit()


def change_password(db: Session, user: User, old_password: str, new_password: str) -> None:
    """修改口令，成功后作废全部刷新令牌。"""
    if not verify_password(old_password, user.password_hash):
        raise BadRequestError("原口令不正确")
    error = password_strength_error(new_password)
    if error:
        raise BadRequestError(error)
    user.password_hash = hash_password(new_password)
    db.commit()
    revoke_all_tokens(db, user.id)


def reset_password(db: Session, user: User, new_password: str) -> None:
    """管理员重置口令。"""
    error = password_strength_error(new_password)
    if error:
        raise BadRequestError(error)
    user.password_hash = hash_password(new_password)
    db.commit()
    revoke_all_tokens(db, user.id)


def create_user(db: Session, username: str, password: str, role: str,
                email: Optional[str] = None, display_name: Optional[str] = None) -> User:
    """新建平台用户。"""
    existing = db.scalar(select(User).where(User.username == username))
    if existing is not None:
        raise ConflictError(f"用户名 {username} 已存在")
    error = password_strength_error(password)
    if error:
        raise BadRequestError(error)
    try:
        role_enum = UserRole(role)
    except ValueError as exc:
        raise BadRequestError(f"非法角色: {role}") from exc

    user = User(
        username=username,
        password_hash=hash_password(password),
        role=role_enum,
        email=email,
        display_name=display_name or username,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
