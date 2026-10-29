"""FastAPI 依赖：数据库会话、当前用户、角色校验、分页。"""
from typing import Annotated, Optional

from fastapi import Depends, Query, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User, UserRole
from app.security.tokens import TokenError, decode_token
from app.utils.errors import ForbiddenError, UnauthorizedError

DbSession = Annotated[Session, Depends(get_db)]


def _extract_token(request: Request) -> Optional[str]:
    """依次从 Authorization 头、access token cookie 中取令牌。"""
    header = request.headers.get("Authorization")
    if header and header.lower().startswith("bearer "):
        return header[7:].strip()
    return request.cookies.get("vi_token")


def get_current_user(request: Request, db: DbSession) -> User:
    """取当前登录用户，未登录抛 401。"""
    token = _extract_token(request)
    if not token:
        raise UnauthorizedError("未登录")
    try:
        payload = decode_token(token, expected_type="access")
    except TokenError as exc:
        raise UnauthorizedError(str(exc)) from exc

    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise UnauthorizedError("账号不可用")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: UserRole):
    """角色校验依赖工厂。

    用法：Depends(require_role(UserRole.ADMIN))
    """
    allowed = set(roles)

    def _checker(user: CurrentUser) -> User:
        if user.role not in allowed:
            names = "/".join(r.value for r in allowed)
            raise ForbiddenError(f"需要以下角色之一: {names}")
        return user

    return _checker


def require_admin(user: CurrentUser) -> User:
    """仅管理员。"""
    if user.role != UserRole.ADMIN:
        raise ForbiddenError("需要 admin 角色")
    return user


def require_operator(user: CurrentUser) -> User:
    """管理员或操作员（可执行写操作）。"""
    if user.role not in (UserRole.ADMIN, UserRole.OPERATOR):
        raise ForbiddenError("需要 admin 或 operator 角色")
    return user


#: 直接用注解声明角色依赖的写法
AdminUser = Annotated[User, Depends(require_admin)]
OperatorUser = Annotated[User, Depends(require_operator)]


class Pagination:
    """分页参数。"""

    def __init__(
        self,
        page: int = Query(1, ge=1, description="页码，从 1 开始"),
        size: int = Query(20, ge=1, le=200, description="每页条数"),
    ):
        self.page = page
        self.size = size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


PageParams = Annotated[Pagination, Depends(Pagination)]
