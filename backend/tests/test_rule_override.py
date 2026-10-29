"""阈值覆盖：默认值 → 全局 → 目标按键覆盖。"""
from app.models.target import RuleSetting, Target, TargetRuleOverride
from app.services.rule_service import effective_config, global_config
from app.vbr.rules import RULE_SPECS


def _target(db, name="t1"):
    target = Target(
        name=name,
        host="10.0.0.1",
        port=9419,
        username="Administrator",
        password_enc="fernet:placeholder",
    )
    db.add(target)
    db.commit()
    db.refresh(target)
    return target


def test_defaults_when_nothing_configured(db):
    target = _target(db)
    cfg = effective_config(db, target.id)
    spec = next(s for s in RULE_SPECS if s.key == "repo.free_space")
    assert cfg["repo.free_space"].params == spec.default_params
    assert cfg["repo.free_space"].enabled is True
    assert cfg["repo.free_space"].level is None


def test_global_then_override_per_key(db):
    target = _target(db)
    db.add(
        RuleSetting(
            rule_key="repo.free_space",
            enabled=False,
            level="critical",
            params_json={"min_free_percent": 50},
        )
    )
    db.add(
        TargetRuleOverride(
            target_id=target.id,
            rule_key="repo.free_space",
            params_json={"min_free_gb": 100},
        )
    )
    db.commit()

    cfg = effective_config(db, target.id)["repo.free_space"]
    # 全局改了一个键、目标覆盖另一个键，未覆盖的键保留规则默认值
    assert cfg.params["min_free_percent"] == 50
    assert cfg.params["min_free_gb"] == 100
    assert cfg.enabled is False
    assert cfg.level == "critical"

    # 全局视图不含目标覆盖
    g = global_config(db)["repo.free_space"]
    assert g.params["min_free_gb"] == 20


def test_target_level_overrides_global(db):
    target = _target(db)
    db.add(
        RuleSetting(
            rule_key="repo.free_space",
            enabled=True,
            level="info",
            params_json={},
        )
    )
    db.add(
        TargetRuleOverride(
            target_id=target.id,
            rule_key="repo.free_space",
            level="warn",
            params_json={},
        )
    )
    db.commit()
    assert effective_config(db, target.id)["repo.free_space"].level == "warn"
