"""数据库种子数据：规则目录、默认告警规则。

全部幂等，应用启动时调用一次即可。
"""
from sqlalchemy.orm import Session

from app.models.alert import AlertRule
from app.services import rule_service


def seed_rules(db: Session) -> int:
    """确保规则目录在库里有一份默认配置，返回新增条数。"""
    rule_service.ensure_seed_rules(db)
    return len(rule_service.global_config(db))


def seed_default_alert_rules(db: Session) -> int:
    """确保存在一条开箱可用的默认告警规则（critical/warn 全部匹配，冷却 60 分钟）。"""
    existing = db.query(AlertRule).filter(AlertRule.name == "默认告警规则").first()
    if existing is not None:
        return 0
    db.add(
        AlertRule(
            name="默认告警规则",
            enabled=True,
            match_rule_key=None,
            match_category=None,
            match_target_ids=None,
            min_level="warn",
            # 没有渠道时规则不会产生通知；用户在前端配置渠道后再补路由
            channel_routes=[],
            cooldown_minutes=60,
            dedup_window_hours=24,
            notify_on_resolve=True,
        )
    )
    db.commit()
    return 1


def run_all(db: Session) -> dict:
    """执行全部种子逻辑。"""
    rules = seed_rules(db)
    alerts = seed_default_alert_rules(db)
    return {"rules": rules, "alert_rules": alerts}
