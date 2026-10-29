"""发现项服务：指纹去重、状态流转、查询。

指纹 = sha1(target_id|rule_key|subject_key)，跨轮次稳定。
一条问题在「当前状态表」中最多一行（按 target_id+fingerprint 唯一），
每次巡检再往历史表追加一行事件，用于回溯问题出现/持续/恢复的过程。
"""
from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.finding import Finding, FindingEvent, FindingStatus
from app.utils.fingerprint import build_fingerprint
from app.utils.timeutil import to_utc_naive, utcnow
from app.vbr.context import Finding as RuleFinding

#: 需要落「当前状态表」的级别；ok 级只计数
PERSISTED_LEVELS = ("critical", "warn", "info")


def sync_findings(
    db: Session,
    target_id: int,
    run_id: int,
    findings: list[RuleFinding],
    now: Optional[datetime] = None,
) -> tuple[list[Finding], list[Finding]]:
    """把本轮发现同步到数据库。

    返回 (本轮命中的发现记录, 本轮恢复的发现记录)。
    恢复的记录用于触发「已恢复」通知。
    """
    now = now or to_utc_naive(utcnow())
    actionable = [f for f in findings if f.level in PERSISTED_LEVELS]
    fingerprints = {
        build_fingerprint(target_id, f.rule_key, f.subject_key) for f in actionable
    }

    existing_rows = db.scalars(
        select(Finding).where(Finding.target_id == target_id)
    ).all()
    by_fp = {row.fingerprint: row for row in existing_rows}

    hit: list[Finding] = []
    for item in actionable:
        fingerprint = build_fingerprint(target_id, item.rule_key, item.subject_key)
        row = by_fp.get(fingerprint)
        if row is None:
            row = Finding(
                target_id=target_id,
                fingerprint=fingerprint,
                rule_key=item.rule_key,
                category=item.category,
                level=item.level,
                subject=item.subject,
                subject_key=item.subject_key,
                message=item.message,
                metric_value=item.metric_value,
                threshold_value=item.threshold_value,
                status=FindingStatus.OPEN,
                occurrences=1,
                first_seen_at=now,
                last_seen_at=now,
                last_run_id=run_id,
            )
            db.add(row)
            by_fp[fingerprint] = row
        else:
            row.occurrences += 1
            row.last_seen_at = now
            row.last_run_id = run_id
            row.level = item.level
            row.message = item.message
            row.metric_value = item.metric_value
            row.threshold_value = item.threshold_value
            # 之前被标记为已恢复的问题再次出现 → 重开
            if row.status == FindingStatus.RESOLVED:
                row.status = FindingStatus.OPEN
                row.resolved_at = None
        hit.append(row)

    db.flush()

    # 本轮没出现、上轮出现过的 → 恢复
    resolved: list[Finding] = []
    for row in existing_rows:
        if row.fingerprint in fingerprints:
            continue
        if row.status == FindingStatus.RESOLVED:
            continue
        row.status = FindingStatus.RESOLVED
        row.resolved_at = now
        resolved.append(row)

    # 追加历史事件
    for row in hit:
        db.add(
            FindingEvent(
                finding_id=row.id,
                run_id=run_id,
                target_id=target_id,
                fingerprint=row.fingerprint,
                level=row.level,
                message=row.message,
                created_at=now,
            )
        )
    for row in resolved:
        db.add(
            FindingEvent(
                finding_id=row.id,
                run_id=run_id,
                target_id=target_id,
                fingerprint=row.fingerprint,
                level=row.level,
                message="问题已恢复",
                created_at=now,
            )
        )

    db.commit()
    for row in hit:
        db.refresh(row)
    for row in resolved:
        db.refresh(row)
    return hit, resolved


def query_findings(
    db: Session,
    target_id: Optional[int] = None,
    level: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    rule_key: Optional[str] = None,
    keyword: Optional[str] = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Finding], int]:
    """按条件查询发现项，返回 (列表, 总数)。"""
    stmt = select(Finding)
    count_stmt = select(func.count(Finding.id))
    conditions = []
    if target_id is not None:
        conditions.append(Finding.target_id == target_id)
    if level:
        conditions.append(Finding.level == level)
    if category:
        conditions.append(Finding.category == category)
    if status:
        conditions.append(Finding.status == status)
    if rule_key:
        conditions.append(Finding.rule_key == rule_key)
    if keyword:
        like = f"%{keyword}%"
        conditions.append((Finding.subject.like(like)) | (Finding.message.like(like)))
    for cond in conditions:
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(
            # 未处理的排前面，同级按最近出现时间倒序
            Finding.status.desc(),
            Finding.last_seen_at.desc(),
        ).offset(offset).limit(limit)
    ).all()
    return list(rows), total


def get_finding(db: Session, finding_id: int) -> Finding:
    """取单条发现项。"""
    row = db.get(Finding, finding_id)
    if row is None:
        from app.utils.errors import NotFoundError

        raise NotFoundError(f"发现项 {finding_id} 不存在")
    return row


def acknowledge(db: Session, finding: Finding, user_id: int) -> Finding:
    """确认（已知悉）发现项。"""
    finding.status = FindingStatus.ACKNOWLEDGED
    finding.acknowledged_by = user_id
    finding.acknowledged_at = to_utc_naive(utcnow())
    db.commit()
    db.refresh(finding)
    return finding


def resolve(db: Session, finding: Finding) -> Finding:
    """手动标记为已恢复。"""
    finding.status = FindingStatus.RESOLVED
    finding.resolved_at = to_utc_naive(utcnow())
    db.commit()
    db.refresh(finding)
    return finding


def bulk_acknowledge(db: Session, user_id: int, finding_ids: Optional[Iterable[int]] = None,
                     target_id: Optional[int] = None) -> int:
    """批量确认。"""
    stmt = select(Finding).where(Finding.status == FindingStatus.OPEN)
    if finding_ids:
        stmt = stmt.where(Finding.id.in_(list(finding_ids)))
    if target_id is not None:
        stmt = stmt.where(Finding.target_id == target_id)
    rows = db.scalars(stmt).all()
    now = to_utc_naive(utcnow())
    for row in rows:
        row.status = FindingStatus.ACKNOWLEDGED
        row.acknowledged_by = user_id
        row.acknowledged_at = now
    db.commit()
    return len(rows)


def summary(db: Session, target_id: Optional[int] = None) -> dict:
    """发现项统计：按级别与状态汇总。"""
    stmt = select(Finding.level, Finding.status, func.count(Finding.id))
    if target_id is not None:
        stmt = stmt.where(Finding.target_id == target_id)
    rows = db.execute(stmt.group_by(Finding.level, Finding.status)).all()

    by_level: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for level, status, count in rows:
        by_level[level] = by_level.get(level, 0) + count
        key = status.value if hasattr(status, "value") else str(status)
        by_status[key] = by_status.get(key, 0) + count
    return {"by_level": by_level, "by_status": by_status}
