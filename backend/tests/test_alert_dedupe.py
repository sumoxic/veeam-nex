"""告警去重：首次投递、冷却期、去重窗口与级别升级。"""
from datetime import timedelta

from sqlalchemy import select

from app.models.alert import AlertEvent, AlertEventStatus, AlertEventType, AlertRule
from app.models.finding import Finding
from app.models.inspection import ClockSource, InspectionRun, RunStatus, RunTrigger
from app.models.target import Target
from app.services.alert_service import dispatch_for_run
from app.utils.fingerprint import build_fingerprint
from app.utils.timeutil import utcnow


def _now():
    return utcnow().replace(tzinfo=None)


def _setup(db):
    target = Target(
        name="t1",
        host="10.0.0.1",
        port=9419,
        username="Administrator",
        password_enc="fernet:placeholder",
    )
    db.add(target)
    db.commit()
    db.refresh(target)

    rule = AlertRule(
        name="磁盘空间",
        enabled=True,
        match_rule_key="repo.free_space",
        min_level="warn",
        channel_routes=[{"channel_id": 1, "min_level": "warn"}],
        cooldown_minutes=60,
        dedup_window_hours=24,
    )
    db.add(rule)
    now = _now()
    run = InspectionRun(
        target_id=target.id,
        trigger_type=RunTrigger.MANUAL,
        status=RunStatus.SUCCESS,
        started_at=now,
        clock_source=ClockSource.VBR,
        created_at=now,
    )
    db.add(run)
    db.commit()
    db.refresh(rule)
    db.refresh(run)

    finding = Finding(
        target_id=target.id,
        fingerprint=build_fingerprint(target.id, "repo.free_space", "repo:g"),
        rule_key="repo.free_space",
        category="repo",
        level="warn",
        subject="仓库 G:\\Backup",
        subject_key="repo:g",
        message="剩余空间不足",
        occurrences=1,
        first_seen_at=now,
        last_seen_at=now,
    )
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return rule, run, finding


def test_first_hit_creates_pending_event(db):
    _, run, finding = _setup(db)
    created = dispatch_for_run(db, run, [finding], [])
    assert len(created) == 1
    assert created[0].status == AlertEventStatus.PENDING
    assert created[0].event_type == AlertEventType.RAISED
    assert created[0].severity == "warn"


def test_cooldown_suppresses_repeat(db):
    _, run, finding = _setup(db)
    first = dispatch_for_run(db, run, [finding], [])[0]
    first.status = AlertEventStatus.SENT
    first.sent_at = _now()
    db.commit()

    assert dispatch_for_run(db, run, [finding], []) == []
    latest = db.scalars(select(AlertEvent).order_by(AlertEvent.id.desc())).first()
    assert latest.status == AlertEventStatus.SUPPRESSED
    assert "冷却" in (latest.error_message or "")


def test_dedup_window_suppresses_after_cooldown(db):
    _, run, finding = _setup(db)
    first = dispatch_for_run(db, run, [finding], [])[0]
    first.status = AlertEventStatus.SENT
    first.sent_at = _now() - timedelta(hours=2)
    db.commit()

    assert dispatch_for_run(db, run, [finding], []) == []
    latest = db.scalars(select(AlertEvent).order_by(AlertEvent.id.desc())).first()
    assert latest.status == AlertEventStatus.SUPPRESSED
    assert "去重窗口" in (latest.error_message or "")


def test_level_escalation_bypasses_dedup(db):
    _, run, finding = _setup(db)
    first = dispatch_for_run(db, run, [finding], [])[0]
    first.status = AlertEventStatus.SENT
    first.sent_at = _now()
    db.commit()

    finding.level = "critical"
    db.commit()
    escalated = dispatch_for_run(db, run, [finding], [])
    assert len(escalated) == 1
    assert escalated[0].event_type == AlertEventType.ESCALATED
    assert escalated[0].status == AlertEventStatus.PENDING
    assert escalated[0].severity == "critical"


def test_rule_match_filters_by_target_and_level(db):
    rule, run, finding = _setup(db)
    rule.match_target_ids = [999]
    db.commit()
    assert dispatch_for_run(db, run, [finding], []) == []

    rule.match_target_ids = None
    rule.min_level = "critical"
    db.commit()
    assert dispatch_for_run(db, run, [finding], []) == []
