"""规则配置服务。

生效配置的优先级：目标覆盖 > 全局配置 > 规则默认值。
目标的 params 按键覆盖全局 params（非覆盖的键保留全局值）。
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.target import RuleSetting, Target, TargetRuleOverride
from app.vbr.context import RuleConfig
from app.vbr.rules import RULE_SPECS


def _global_settings(db: Session) -> dict[str, RuleSetting]:
    """全部全局规则配置。"""
    rows = db.scalars(select(RuleSetting)).all()
    return {row.rule_key: row for row in rows}


def _overrides(db: Session, target_id: int) -> dict[str, TargetRuleOverride]:
    """某目标的全部规则覆盖。"""
    rows = db.scalars(
        select(TargetRuleOverride).where(TargetRuleOverride.target_id == target_id)
    ).all()
    return {row.rule_key: row for row in rows}


def effective_config(db: Session, target_id: int) -> dict[str, RuleConfig]:
    """计算某目标的规则生效配置。"""
    globals_ = _global_settings(db)
    overrides = _overrides(db, target_id)

    config: dict[str, RuleConfig] = {}
    for spec in RULE_SPECS:
        g = globals_.get(spec.key)
        o = overrides.get(spec.key)

        params = dict(spec.default_params)
        enabled = True
        level: Optional[str] = None

        if g is not None:
            params.update(g.params_json or {})
            enabled = g.enabled
            level = g.level

        if o is not None:
            params.update(o.params_json or {})
            if o.enabled is not None:
                enabled = o.enabled
            if o.level is not None:
                level = o.level

        config[spec.key] = RuleConfig(enabled=enabled, level=level, params=params)
    return config


def global_config(db: Session) -> dict[str, RuleConfig]:
    """全局规则配置（不含目标覆盖）。"""
    globals_ = _global_settings(db)
    config: dict[str, RuleConfig] = {}
    for spec in RULE_SPECS:
        g = globals_.get(spec.key)
        params = dict(spec.default_params)
        enabled = True
        level: Optional[str] = None
        if g is not None:
            params.update(g.params_json or {})
            enabled = g.enabled
            level = g.level
        config[spec.key] = RuleConfig(enabled=enabled, level=level, params=params)
    return config


def set_global_rule(db: Session, rule_key: str, enabled: Optional[bool],
                    level: Optional[str], params: Optional[dict],
                    updated_by: Optional[int] = None) -> RuleSetting:
    """设置全局规则配置。"""
    row = db.get(RuleSetting, rule_key)
    if row is None:
        row = RuleSetting(rule_key=rule_key, enabled=True, params_json={})
        db.add(row)
    if enabled is not None:
        row.enabled = enabled
    if level is not None:
        row.level = level
    if params is not None:
        row.params_json = params
    row.updated_by = updated_by
    db.commit()
    db.refresh(row)
    return row


def reset_global_rules(db: Session) -> None:
    """把全局规则配置恢复为默认值。"""
    db.query(RuleSetting).delete()
    db.commit()


def set_target_override(db: Session, target_id: int, rule_key: str,
                        enabled: Optional[bool], level: Optional[str],
                        params: Optional[dict], updated_by: Optional[int] = None) -> TargetRuleOverride:
    """设置某目标的规则覆盖。"""
    row = db.scalar(
        select(TargetRuleOverride).where(
            TargetRuleOverride.target_id == target_id,
            TargetRuleOverride.rule_key == rule_key,
        )
    )
    if row is None:
        row = TargetRuleOverride(target_id=target_id, rule_key=rule_key, params_json={})
        db.add(row)
    if enabled is not None:
        row.enabled = enabled
    if level is not None:
        row.level = level
    if params is not None:
        row.params_json = params
    row.updated_by = updated_by
    db.commit()
    db.refresh(row)
    return row


def clear_target_override(db: Session, target_id: int, rule_key: str) -> None:
    """删除某目标的规则覆盖，回落到全局配置。"""
    db.query(TargetRuleOverride).filter(
        TargetRuleOverride.target_id == target_id,
        TargetRuleOverride.rule_key == rule_key,
    ).delete()
    db.commit()


def ensure_seed_rules(db: Session) -> None:
    """确保规则目录在库里有一份默认配置（幂等）。"""
    existing = {row.rule_key for row in db.scalars(select(RuleSetting)).all()}
    for spec in RULE_SPECS:
        if spec.key not in existing:
            db.add(
                RuleSetting(
                    rule_key=spec.key,
                    enabled=True,
                    level=None,
                    params_json=dict(spec.default_params),
                    description=spec.description,
                )
            )
    db.commit()
