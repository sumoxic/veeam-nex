"""规则接口：目录、全局配置、目标覆盖。"""
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.deps import DbSession, OperatorUser
from app.models.target import TargetRuleOverride
from app.schemas.rule import RuleConfigIn, RuleSettingOut
from app.services import rule_service
from app.utils.errors import NotFoundError, ok
from app.vbr.rules import catalogue, get_spec

router = APIRouter(tags=["巡检规则"])


@router.get("/rules", summary="规则目录")
def list_rules() -> dict:
    """返回全部巡检规则的元数据与参数定义。"""
    items = catalogue()
    return ok({"items": items, "total": len(items)})


@router.get("/rules/config", summary="全局规则配置")
def get_global_config(db: DbSession) -> dict:
    """返回全局生效配置（默认值 + 全局覆盖）。"""
    config = rule_service.global_config(db)
    items = [
        {
            "rule_key": key,
            "enabled": cfg.enabled,
            "level": cfg.level,
            "params": cfg.params,
        }
        for key, cfg in config.items()
    ]
    return ok({"items": items, "total": len(items)})


@router.put("/rules/{rule_key}", summary="修改全局规则配置")
def update_global_rule(rule_key: str, payload: RuleConfigIn, db: DbSession,
                       user: OperatorUser) -> dict:
    """设置某条规则的启用状态、级别与阈值。"""
    spec = get_spec(rule_key)
    if spec is None:
        raise NotFoundError(f"规则 {rule_key} 不存在")
    row = rule_service.set_global_rule(
        db, rule_key, payload.enabled, payload.level, payload.params, user.id
    )
    return ok(RuleSettingOut.model_validate(row).model_dump())


@router.post("/rules/reset", summary="重置全局规则配置")
def reset_rules(db: DbSession, user: OperatorUser) -> dict:
    """把全局规则配置恢复为规则默认值。"""
    rule_service.reset_global_rules(db)
    rule_service.ensure_seed_rules(db)
    return ok({"message": "全局规则配置已恢复默认"})


@router.get("/targets/{target_id}/rules", summary="目标的生效规则配置")
def target_rules(target_id: int, db: DbSession) -> dict:
    """返回某目标的生效配置（目标覆盖 > 全局 > 默认）。"""
    config = rule_service.effective_config(db, target_id)
    items = [
        {
            "rule_key": key,
            "enabled": cfg.enabled,
            "level": cfg.level,
            "params": cfg.params,
        }
        for key, cfg in config.items()
    ]
    return ok({"items": items, "total": len(items)})


@router.get("/targets/{target_id}/rules/{rule_key}", summary="目标的规则覆盖")
def get_target_override(target_id: int, rule_key: str, db: DbSession) -> dict:
    """取某目标对某条规则的覆盖配置。"""
    row = db.scalar(
        select(TargetRuleOverride).where(
            TargetRuleOverride.target_id == target_id,
            TargetRuleOverride.rule_key == rule_key,
        )
    )
    if row is None:
        raise NotFoundError(f"目标 {target_id} 未覆盖规则 {rule_key}")
    return ok(
        {
            "target_id": row.target_id,
            "rule_key": row.rule_key,
            "enabled": row.enabled,
            "level": row.level,
            "params": row.params_json,
        }
    )


@router.put("/targets/{target_id}/rules/{rule_key}", summary="设置目标的规则覆盖")
def set_target_override(target_id: int, rule_key: str, payload: RuleConfigIn, db: DbSession,
                        user: OperatorUser) -> dict:
    """设置某目标对某条规则的覆盖；params 按键覆盖全局值。"""
    if get_spec(rule_key) is None:
        raise NotFoundError(f"规则 {rule_key} 不存在")
    row = rule_service.set_target_override(
        db, target_id, rule_key, payload.enabled, payload.level, payload.params, user.id
    )
    return ok(
        {
            "target_id": row.target_id,
            "rule_key": row.rule_key,
            "enabled": row.enabled,
            "level": row.level,
            "params": row.params_json,
        }
    )


@router.delete("/targets/{target_id}/rules/{rule_key}", summary="清除目标的规则覆盖")
def clear_target_override(target_id: int, rule_key: str, db: DbSession,
                          user: OperatorUser) -> dict:
    """删除覆盖配置，回落到全局设置。"""
    rule_service.clear_target_override(db, target_id, rule_key)
    return ok({"message": "规则覆盖已清除"})
