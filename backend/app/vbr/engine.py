"""巡检引擎：按生效配置执行规则，产出发现项。

单条规则出错只降级为一条 error，不会中断整轮巡检。
"""
from app.core.logging import logger
from app.vbr.context import Finding, InspectionContext, iter_entities
from app.vbr.rules import RULE_SPECS


def run(ctx: InspectionContext) -> tuple[list[Finding], list[str]]:
    """执行全部启用的规则。

    返回 (发现项列表, 错误列表)。
    """
    findings: list[Finding] = []
    errors: list[str] = []

    for spec in RULE_SPECS:
        cfg = ctx.config.get(spec.key)
        if cfg is not None and not cfg.enabled:
            continue

        params = ctx.params(spec.key)
        try:
            if spec.collection is None:
                findings.extend(spec.fn(ctx, params, {}))
            else:
                for entity in iter_entities(ctx, spec.collection):
                    findings.extend(spec.fn(ctx, params, entity))
        except Exception as exc:  # noqa: BLE001 —— 单条规则失败不应中断整轮
            message = f"规则 {spec.key} 执行失败: {exc}"
            errors.append(message)
            logger.warning("rule execution failed", extra={"rule_key": spec.key, "error": str(exc)})

    return findings, errors
