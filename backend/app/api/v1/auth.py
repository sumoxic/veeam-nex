"""认证接口：登录、刷新、登出、当前用户、改密。"""
from fastapi import APIRouter, Request, Response

from app.deps import CurrentUser, DbSession
from app.schemas.auth import LoginIn, PasswordChangeIn, TokenOut, UserOut
from app.services import auth_service
from app.utils.errors import ok

router = APIRouter(prefix="/auth", tags=["认证"])


def _set_auth_cookies(response: Response, tokens: dict) -> None:
    """把令牌写入 HttpOnly cookie，兼顾浏览器与 curl 两种用法。"""
    response.set_cookie(
        auth_service.COOKIE_ACCESS,
        tokens["access_token"],
        httponly=True,
        samesite="lax",
        max_age=tokens["expires_in"],
        path="/",
    )
    if tokens.get("refresh_token"):
        response.set_cookie(
            auth_service.COOKIE_REFRESH,
            tokens["refresh_token"],
            httponly=True,
            samesite="lax",
            max_age=7 * 24 * 3600,
            path="/",
        )


@router.post("/login", summary="登录")
def login(payload: LoginIn, response: Response, db: DbSession) -> dict:
    """账号口令换取访问令牌。"""
    user = auth_service.authenticate(db, payload.username, payload.password)
    tokens = auth_service.issue_tokens(db, user)
    _set_auth_cookies(response, tokens)
    return ok({**tokens, "user": UserOut.model_validate(user).model_dump()})


@router.post("/refresh", summary="刷新令牌")
def refresh(request: Request, response: Response, db: DbSession) -> dict:
    """用刷新令牌换取新的访问令牌，并轮换刷新令牌。"""
    token = request.cookies.get(auth_service.COOKIE_REFRESH)
    if not token:
        header = request.headers.get("X-Refresh-Token")
        token = header
    if not token:
        from app.utils.errors import UnauthorizedError

        raise UnauthorizedError("缺少刷新令牌")
    user, tokens = auth_service.rotate_refresh_token(db, token)
    _set_auth_cookies(response, tokens)
    return ok({**tokens, "user": UserOut.model_validate(user).model_dump()})


@router.post("/logout", summary="登出")
def logout(request: Request, response: Response, db: DbSession) -> dict:
    """作废刷新令牌并清除 cookie。"""
    token = request.cookies.get(auth_service.COOKIE_REFRESH)
    if token:
        auth_service.revoke_refresh_token(db, token)
    response.delete_cookie(auth_service.COOKIE_ACCESS, path="/")
    response.delete_cookie(auth_service.COOKIE_REFRESH, path="/")
    return ok({"message": "已登出"})


@router.get("/me", summary="当前用户")
def me(user: CurrentUser) -> dict:
    """返回当前登录用户信息。"""
    return ok(UserOut.model_validate(user).model_dump())


@router.post("/password", summary="修改口令")
def change_password(payload: PasswordChangeIn, user: CurrentUser, db: DbSession) -> dict:
    """修改自己的口令，成功后所有会话需要重新登录。"""
    auth_service.change_password(db, user, payload.old_password, payload.new_password)
    return ok({"message": "口令已修改，请重新登录"})
