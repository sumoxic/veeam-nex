"""告警规则接口。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.deps import DbSession, OperatorUser
from app.models.alert import AlertRule
from app.schemas.alert import AlertRuleIn, AlertRuleOut
from app.utils.errors import NotFoundError, ok

router = APIRouter(prefix="/alert-rules", tags=["告警规则"])


def _out(row: AlertRule) -> dict:
    return AlertRuleOut.model_validate(row).model_dump()


@router.get("", summary="告警规则列表")
def list_alert_rules(db: DbSession) -> dict:
    """列出全部告警规则。"""
    rows = db.scalars(select(AlertRule).order_by(AlertRule.id)).all()
    return ok({"items": [_out(r) for r in rows], "total": len(rows)})


@router.post("", summary="新建告警规则")
def create_alert_rule(payload: AlertRuleIn, db: DbSession,
                      user: OperatorUser) -> dict:
    """新建一条告警规则。"""
    data = payload.model_dump()
    data["channel_routes"] = [r if isinstance(r, dict) else r.model_dump()
                              for r in payload.channel_routes]
    row = AlertRule(created_by=user.id, updated_by=user.id, **data)
    db.add(row)
    db.commit()
    db.refresh(row)
    return ok(_out(row))


@router.get("/{rule_id}", summary="告警规则详情")
def get_alert_rule(rule_id: int, db: DbSession) -> dict:
    """取单条告警规则。"""
    row = db.get(AlertRule, rule_id)
    if row is None:
        raise NotFoundError(f"告警规则 {rule_id} 不存在")
    return ok(_out(row))


@router.put("/{rule_id}", summary="修改告警规则")
def update_alert_rule(rule_id: int, payload: AlertRuleIn, db: DbSession,
                      user: OperatorUser) -> dict:
    """修改告警规则。"""
    row = db.get(AlertRule, rule_id)
    if row is None:
        raise NotFoundError(f"告警规则 {rule_id} 不存在")
    data = payload.model_dump()
    data["channel_routes"] = [r if isinstance(r, dict) else r.model_dump()
                              for r in payload.channel_routes]
    for key, value in data.items():
        setattr(row, key, value)
    row.updated_by = user.id
    db.commit()
    db.refresh(row)
    return ok(_out(row))


@router.delete("/{rule_id}", summary="删除告警规则")
def delete_alert_rule(rule_id: int, db: DbSession,
                      user: OperatorUser) -> dict:
    """删除告警规则（其下的告警事件随外键级联清理）。"""
    row = db.get(AlertRule, rule_id)
    if row is None:
        raise NotFoundError(f"告警规则 {rule_id} 不存在")
    db.delete(row)
    db.commit()
    return ok({"message": "告警规则已删除"})


@router.post("/{rule_id}/test", summary="测试告警规则")
def test_alert_rule(rule_id: int, db: DbSession,
                    user: OperatorUser) -> dict:
    """按该规则构造一条测试事件并投递，用于验证渠道连通性。"""
    from app.models.alert import AlertEvent, AlertEventStatus, AlertEventType
    from app.utils.fingerprint import build_dedup_key
    from app.utils.timeutil import to_utc_naive, utcnow

    row = db.get(AlertRule, rule_id)
    if row is None:
        raise NotFoundError(f"告警规则 {rule_id} 不存在")

    routes = row.channel_routes or []
    if not routes:
        return ok({"sent": 0, "message": "该规则没有配置路由渠道"})

    now = to_utc_naive(utcnow())
    created = 0
    for route in routes:
        channel_id = route.get("channel_id")
        if channel_id is None:
            continue
        db.add(
            AlertEvent(
                alert_rule_id=row.id,
                channel_id=int(channel_id),
                fingerprint="test-fingerprint",
                dedup_key=build_dedup_key(row.id, "test-fingerprint"),
                event_type=AlertEventType.RAISED,
                severity="info",
                title="Veeam 巡检平台告警规则测试",
                body=f"告警规则「{row.name}」的测试通知。",
                status=AlertEventStatus.PENDING,
                created_at=now,
            )
        )
        created += 1
    db.commit()

    from app.notifications import dispatcher

    stats = dispatcher.dispatch_pending(db)
    return ok({"created": created, **stats})
