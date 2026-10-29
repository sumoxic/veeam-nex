"""告警服务：规则匹配、去重/冷却、投递事件生成。

流程（每轮巡检结束时调用）：
    发现项 → 匹配告警规则 → 判定去重/冷却 → 落 pending 告警事件 → 由调度器投递
被去重或冷却拦下的事件同样落库（status=suppressed），让运维看得见「为什么没发」。
"""
from datetime import timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.alert import (
    AlertEvent,
    AlertEventStatus,
    AlertEventType,
    AlertRule,
    NotificationChannel,
)
from app.models.finding import Finding
from app.models.inspection import InspectionRun
from app.models.target import Target
from app.utils.fingerprint import build_dedup_key
from app.utils.timeutil import to_utc_naive, utcnow
from app.vbr.context import LEVEL_ORDER

#: 单次投递的最大重试次数
MAX_ATTEMPTS = 3


def _matches(rule: AlertRule, finding: Finding, target_id: int) -> bool:
    """判断一条发现是否命中某条告警规则。"""
    if rule.match_rule_key:
        if finding.rule_key != rule.match_rule_key:
            return False
    elif rule.match_category:
        if finding.category != rule.match_category:
            return False
    else:
        # 既不按规则也不按类别 → 视为全量匹配，交给级别与目标条件过滤
        pass

    target_ids = rule.match_target_ids or []
    if target_ids and target_id not in target_ids:
        return False

    if LEVEL_ORDER.get(finding.level, 0) < LEVEL_ORDER.get(rule.min_level, 0):
        return False
    return True


def _route_channels(rule: AlertRule, finding: Finding) -> list[tuple[int, str]]:
    """按路由表算出需要投递的渠道及其级别门槛。"""
    routes = rule.channel_routes or []
    result: list[tuple[int, str]] = []
    for route in routes:
        channel_id = route.get("channel_id")
        if channel_id is None:
            continue
        min_level = route.get("min_level") or rule.min_level
        if LEVEL_ORDER.get(finding.level, 0) < LEVEL_ORDER.get(min_level, 0):
            continue
        result.append((int(channel_id), min_level))
    return result


def _last_sent_event(db: Session, dedup_key: str) -> Optional[AlertEvent]:
    """取该去重键最近一次成功投递的事件。"""
    return db.scalar(
        select(AlertEvent)
        .where(AlertEvent.dedup_key == dedup_key, AlertEvent.status == AlertEventStatus.SENT)
        .order_by(AlertEvent.created_at.desc())
        .limit(1)
    )


def _build_message(finding: Finding, target_name: str, event_type: str) -> tuple[str, str]:
    """生成标题与正文。"""
    prefix = {"raised": "发现", "escalated": "级别升高", "resolved": "已恢复"}[event_type]
    title = f"[{finding.level.upper()}] {target_name} · {prefix}: {finding.subject}"
    lines = [
        f"目标: {target_name}",
        f"规则: {finding.rule_key}",
        f"级别: {finding.level}",
        f"问题: {finding.message}",
    ]
    if finding.metric_value is not None:
        lines.append(f"实测值: {finding.metric_value}")
    if finding.threshold_value is not None:
        lines.append(f"阈值: {finding.threshold_value}")
    lines.append(f"累计出现: {finding.occurrences} 次")
    return title, "\n".join(lines)


def dispatch_for_run(
    db: Session,
    run: InspectionRun,
    hit: list[Finding],
    resolved: list[Finding],
) -> list[AlertEvent]:
    """本轮巡检的发现项与恢复项分发生警事件，返回新建的事件列表。"""
    now = to_utc_naive(utcnow())
    rules = list(
        db.scalars(select(AlertRule).where(AlertRule.enabled.is_(True))).all()
    )
    if not rules:
        return []

    target_name = db.get(Target, run.target_id).name if run.target_id else "未知目标"
    created: list[AlertEvent] = []

    def _emit(rule: AlertRule, finding: Finding, channel_id: int,
              event_type: str, severity: str) -> None:
        title, body = _build_message(finding, target_name, event_type)
        event = AlertEvent(
            alert_rule_id=rule.id,
            channel_id=channel_id,
            target_id=finding.target_id,
            finding_id=finding.id,
            run_id=run.id,
            fingerprint=finding.fingerprint,
            dedup_key=build_dedup_key(rule.id, finding.fingerprint),
            event_type=AlertEventType(event_type),
            severity=severity,
            title=title,
            body=body,
            status=AlertEventStatus.PENDING,
            created_at=now,
        )
        db.add(event)
        created.append(event)

    # ---- 新增/持续的问题 ----
    for finding in hit:
        for rule in rules:
            if not _matches(rule, finding, run.target_id):
                continue
            for channel_id, _ in _route_channels(rule, finding):
                dedup_key = build_dedup_key(rule.id, finding.fingerprint)
                last = _last_sent_event(db, dedup_key)
                event_type = "raised"
                if last is not None:
                    escalated = LEVEL_ORDER.get(finding.level, 0) > LEVEL_ORDER.get(
                        last.severity, 0
                    )
                    if escalated:
                        # 级别升高：绕过去重与冷却，立即投递
                        event_type = "escalated"
                    else:
                        since = now - (last.sent_at or last.created_at)
                        if since < timedelta(minutes=rule.cooldown_minutes):
                            _emit_suppressed(db, rule, finding, channel_id, now,
                                             "冷却期内不重复通知")
                            continue
                        if since < timedelta(hours=rule.dedup_window_hours):
                            _emit_suppressed(db, rule, finding, channel_id, now,
                                             "去重窗口内已通知")
                            continue
                _emit(rule, finding, channel_id, event_type, finding.level)

    # ---- 恢复的问题 ----
    for finding in resolved:
        for rule in rules:
            if not rule.notify_on_resolve:
                continue
            if not _matches(rule, finding, run.target_id):
                continue
            for channel_id, _ in _route_channels(rule, finding):
                _emit(rule, finding, channel_id, "resolved", finding.level)

    db.commit()
    for event in created:
        db.refresh(event)
    if created:
        logger.info(
            "alert events created",
            extra={"run_id": run.id, "target_id": run.target_id, "count": len(created)},
        )
    return created


def _emit_suppressed(db: Session, rule: AlertRule, finding: Finding,
                     channel_id: int, now, reason: str) -> None:
    """落一条 suppressed 事件，说明本次为什么没发。"""
    db.add(
        AlertEvent(
            alert_rule_id=rule.id,
            channel_id=channel_id,
            target_id=finding.target_id,
            finding_id=finding.id,
            fingerprint=finding.fingerprint,
            dedup_key=build_dedup_key(rule.id, finding.fingerprint),
            event_type=AlertEventType.RAISED,
            severity=finding.level,
            title=finding.subject,
            body=reason,
            status=AlertEventStatus.SUPPRESSED,
            error_message=reason,
            created_at=now,
        )
    )
    db.commit()


def list_events(
    db: Session,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    target_id: Optional[int] = None,
    alert_rule_id: Optional[int] = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[AlertEvent], int]:
    """分页查询告警事件。"""
    from sqlalchemy import func

    stmt = select(AlertEvent)
    count_stmt = select(func.count(AlertEvent.id))
    conditions = []
    if status:
        conditions.append(AlertEvent.status == status)
    if severity:
        conditions.append(AlertEvent.severity == severity)
    if target_id is not None:
        conditions.append(AlertEvent.target_id == target_id)
    if alert_rule_id is not None:
        conditions.append(AlertEvent.alert_rule_id == alert_rule_id)
    for cond in conditions:
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(AlertEvent.created_at.desc()).offset(offset).limit(limit)
    ).all()
    return list(rows), total
