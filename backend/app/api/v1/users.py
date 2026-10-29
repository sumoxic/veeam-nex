"""用户管理接口（仅管理员）。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.deps import DbSession, require_admin
from app.models.user import User
from app.schemas.auth import PasswordResetIn, UserCreateIn, UserOut, UserUpdateIn
from app.services import auth_service
from app.utils.errors import BadRequestError, NotFoundError, ok

router = APIRouter(prefix="/users", tags=["用户管理"], dependencies=[Depends(require_admin)])


@router.get("", summary="用户列表")
def list_users(db: DbSession) -> dict:
    """列出全部平台用户。"""
    users = db.scalars(select(User).order_by(User.id)).all()
    return ok({"items": [UserOut.model_validate(u).model_dump() for u in users]})


@router.post("", summary="新建用户")
def create_user(payload: UserCreateIn, db: DbSession) -> dict:
    """新建平台用户。"""
    user = auth_service.create_user(
        db,
        username=payload.username,
        password=payload.password,
        role=payload.role,
        email=payload.email,
        display_name=payload.display_name,
    )
    return ok(UserOut.model_validate(user).model_dump())


@router.get("/{user_id}", summary="用户详情")
def get_user(user_id: int, db: DbSession) -> dict:
    """取单个用户。"""
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError(f"用户 {user_id} 不存在")
    return ok(UserOut.model_validate(user).model_dump())


@router.put("/{user_id}", summary="修改用户")
def update_user(user_id: int, payload: UserUpdateIn, db: DbSession) -> dict:
    """修改用户的资料、角色与启用状态。"""
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError(f"用户 {user_id} 不存在")

    if payload.email is not None:
        user.email = payload.email or None
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.role is not None:
        from app.models.user import UserRole

        try:
            user.role = UserRole(payload.role)
        except ValueError as exc:
            raise BadRequestError(f"非法角色: {payload.role}") from exc
    if payload.is_active is not None:
        user.is_active = payload.is_active
        if not payload.is_active:
            auth_service.revoke_all_tokens(db, user.id)

    db.commit()
    db.refresh(user)
    return ok(UserOut.model_validate(user).model_dump())


@router.delete("/{user_id}", summary="停用用户")
def deactivate_user(user_id: int, db: DbSession) -> dict:
    """停用（不物理删除，保留历史关联）。"""
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError(f"用户 {user_id} 不存在")
    user.is_active = False
    db.commit()
    auth_service.revoke_all_tokens(db, user.id)
    return ok({"message": "用户已停用"})


@router.post("/{user_id}/reset-password", summary="重置口令")
def reset_password(user_id: int, payload: PasswordResetIn, db: DbSession) -> dict:
    """重置指定用户的口令。"""
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError(f"用户 {user_id} 不存在")
    auth_service.reset_password(db, user, payload.new_password)
    return ok({"message": "口令已重置"})
