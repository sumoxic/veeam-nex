"""告警投递器：把 pending 事件真正发出去，并处理失败重试。"""
from datetime import timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.alert import AlertEvent, AlertEventStatus
from app.notifications.base import Message, NotifyError
from app.services import channel_service
from app.utils.timeutil import to_utc_naive, utcnow

#: 各级重试的等待时长（秒）：60 / 300 / 900
BACKOFF_SECONDS = (60, 300, 900)

#: 最大尝试次数
MAX_ATTEMPTS = 3


def _next_attempt_at(event: AlertEvent):
    """按已尝试次数算出下次可发送的时间。"""
    if event.attempts <= 0:
        return event.created_at
    index = min(event.attempts, len(BACKOFF_SECONDS)) - 1
    return event.created_at + timedelta(seconds=BACKOFF_SECONDS[index])


def pending_events(db: Session, limit: int = 20) -> list[AlertEvent]:
    """取当前可以尝试投递的事件（已过退避时间且未超次数）。"""
    now = to_utc_naive(utcnow())
    rows = db.scalars(
        select(AlertEvent)
        .where(AlertEvent.status == AlertEventStatus.PENDING)
        .order_by(AlertEvent.created_at.asc())
        .limit(limit * 3)
    ).all()
    return [r for r in rows if r.attempts < MAX_ATTEMPTS and _next_attempt_at(r) <= now][:limit]


def send_event(db: Session, event: AlertEvent) -> bool:
    """尝试投递一条事件，成功返回 True。"""
    now = to_utc_naive(utcnow())
    event.attempts += 1
    try:
        channel = channel_service.get_channel(db, event.channel_id)
        if not channel.enabled:
            raise NotifyError("渠道已停用")
        message = Message(
            title=event.title or "Veeam 巡检告警",
            body=event.body or "",
            severity=event.severity,
        )
        channel_service.build_notifier(channel).send(message)
    except Exception as exc:  # noqa: BLE001 —— 投递失败不能拖垮调度器
        event.error_message = str(exc)[:2000]
        if event.attempts >= MAX_ATTEMPTS:
            event.status = AlertEventStatus.FAILED
            logger.error(
                "alert event failed permanently",
                extra={"event_id": event.id, "attempts": event.attempts, "error": str(exc)},
            )
        else:
            logger.warning(
                "alert event send failed, will retry",
                extra={"event_id": event.id, "attempts": event.attempts, "error": str(exc)},
            )
        db.commit()
        return False

    event.status = AlertEventStatus.SENT
    event.sent_at = now
    event.error_message = None
    db.commit()
    logger.info(
        "alert event sent",
        extra={"event_id": event.id, "channel_id": event.channel_id},
    )
    return True


def dispatch_pending(db: Session, limit: int = 20) -> dict:
    """排空 pending 队列，返回本轮投递统计。"""
    events = pending_events(db, limit)
    sent = failed = 0
    for event in events:
        if send_event(db, event):
            sent += 1
        else:
            failed += 1
    return {"total": len(events), "sent": sent, "failed": failed}


def retry_event(db: Session, event: AlertEvent) -> bool:
    """手动重试一条失败/抑制的事件。"""
    event.status = AlertEventStatus.PENDING
    event.attempts = 0
    event.created_at = to_utc_naive(utcnow())
    db.commit()
    return send_event(db, event)
