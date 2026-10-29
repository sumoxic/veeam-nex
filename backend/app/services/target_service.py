"""巡检目标服务：增删改查、凭据解密、连通性测试、能力探测缓存。"""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.target import Target
from app.security.crypto import decrypt, encrypt
from app.utils.errors import ConflictError, NotFoundError
from app.utils.timeutil import to_utc_naive, utcnow
from app.vbr.client import VbrClient
from app.vbr.exceptions import AuthError, VbrError

#: 能力探测结果的缓存时长
CAPABILITY_TTL = timedelta(hours=1)


def get_target(db: Session, target_id: int) -> Target:
    """取目标，不存在则抛 404。"""
    target = db.get(Target, target_id)
    if target is None:
        raise NotFoundError(f"巡检目标 {target_id} 不存在")
    return target


def list_targets(db: Session, enabled: Optional[bool] = None,
                 keyword: Optional[str] = None) -> list[Target]:
    """按条件列出目标。"""
    stmt = select(Target)
    if enabled is not None:
        stmt = stmt.where(Target.is_enabled == enabled)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where((Target.name.like(like)) | (Target.host.like(like)))
    return list(db.scalars(stmt.order_by(Target.id)).all())


def create_target(db: Session, **fields) -> Target:
    """新建目标（口令加密存储）。"""
    existing = db.scalar(select(Target).where(Target.name == fields["name"]))
    if existing is not None:
        raise ConflictError(f"目标名称 {fields['name']} 已存在")

    password = fields.pop("password")
    target = Target(
        **fields,
        password_enc=encrypt(password),
    )
    db.add(target)
    db.commit()
    db.refresh(target)
    return target


def update_target(db: Session, target: Target, **fields) -> Target:
    """更新目标；只有传了 password 才会重写口令密文。"""
    password = fields.pop("password", None)
    if password:
        target.password_enc = encrypt(password)
    for key, value in fields.items():
        if value is not None:
            setattr(target, key, value)
    db.commit()
    db.refresh(target)
    return target


def delete_target(db: Session, target: Target) -> None:
    """删除目标（级联清理运行记录、发现项等）。"""
    db.delete(target)
    db.commit()


def build_client(target: Target) -> VbrClient:
    """用目标配置构造 VBR 客户端（口令在此解密）。"""
    return VbrClient(
        host=target.host,
        port=target.port,
        username=target.username,
        password=decrypt(target.password_enc),
        verify_tls=target.verify_tls,
    )


def test_connection(target: Target) -> dict:
    """测试与 VBR 的连通性，返回服务器信息与时钟。"""
    try:
        client = build_client(target)
        server = client.get("/api/v1/serverInfo")
        server_time = client.get("/api/v1/serverTime")
        return {
            "ok": True,
            "server": server if isinstance(server, dict) else {},
            "server_time": (server_time or {}).get("serverTime")
            if isinstance(server_time, dict)
            else None,
            "iana_tz": (server_time or {}).get("ianaTimeZoneId")
            if isinstance(server_time, dict)
            else None,
            "error": None,
        }
    except AuthError as exc:
        return {"ok": False, "server": {}, "server_time": None, "iana_tz": None,
                "error": f"认证失败: {exc}"}
    except VbrError as exc:
        return {"ok": False, "server": {}, "server_time": None, "iana_tz": None,
                "error": str(exc)}


def get_capabilities(db: Session, target: Target, force: bool = False) -> dict:
    """取能力探测结果（带 1 小时缓存）。

    available() 需要 14 次 HTTP 调用，不能每次巡检都跑。
    """
    now = to_utc_naive(utcnow())
    cached = target.capabilities_json
    checked_at = target.capabilities_checked_at
    fresh = (
        cached is not None
        and checked_at is not None
        and checked_at > now - CAPABILITY_TTL
    )
    if fresh and not force:
        return cached

    try:
        client = build_client(target)
        result = client.available()
    except VbrError as exc:
        logger.warning("capability probe failed", extra={"target_id": target.id, "error": str(exc)})
        return cached or {}

    target.capabilities_json = result
    target.capabilities_checked_at = now
    db.commit()
    return result


def update_schedule(db: Session, target: Target, cron: Optional[str],
                    timezone: str, enabled: bool) -> Target:
    """更新排期配置（排期的权威数据源在数据库）。"""
    target.schedule_cron = cron
    target.schedule_timezone = timezone
    target.schedule_enabled = bool(enabled and cron)
    db.commit()
    db.refresh(target)
    return target
