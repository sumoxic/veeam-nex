"""巡检发现项与其历史事件。"""
import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UTCDateTime


class FindingLevel(str, enum.Enum):
    """发现项级别。ok 级不落表，只计数。"""

    CRITICAL = "critical"
    WARN = "warn"
    INFO = "info"
    OK = "ok"


class FindingStatus(str, enum.Enum):
    """发现项状态机：open → acknowledged → resolved（再次出现则重开）。"""

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class Finding(Base, TimestampMixin):
    """当前状态下的一个巡检问题。

    fingerprint = sha1(target_id|rule_key|subject_key)，跨轮稳定，
    是去重与「问题是否恢复」判断的基础。
    """

    __tablename__ = "findings"
    __table_args__ = (
        UniqueConstraint("target_id", "fingerprint", name="uq_findings_target_fp"),
        Index("idx_findings_target_level", "target_id", "level", "status"),
        Index("idx_findings_target_cat", "target_id", "category"),
        Index("idx_findings_rule", "rule_key"),
        Index("idx_findings_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("targets.id", ondelete="CASCADE"), nullable=False
    )
    fingerprint: Mapped[str] = mapped_column(String(40), nullable=False)
    rule_key: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    #: 机器可读的对象标识，如 "job:<uuid>"；不能用会变化的消息文本
    subject_key: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metric_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    threshold_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[FindingStatus] = mapped_column(
        Enum(FindingStatus, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=FindingStatus.OPEN,
    )
    #: 连续多少轮巡检都命中该问题
    occurrences: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    last_run_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("inspection_runs.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    acknowledged_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)

    events: Mapped[list["FindingEvent"]] = relationship(
        back_populates="finding", cascade="all, delete-orphan"
    )


class FindingEvent(Base):
    """发现项历史事件（只追加）。

    每次巡检对每个发现写一行，用于「问题出现/持续/恢复」的历史回溯。
    """

    __tablename__ = "finding_events"
    __table_args__ = (
        Index("idx_fe_run", "run_id"),
        Index("idx_fe_finding", "finding_id", "created_at"),
        Index("idx_fe_fp_time", "fingerprint", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    finding_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("findings.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("inspection_runs.id", ondelete="CASCADE"), nullable=False
    )
    target_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("targets.id", ondelete="CASCADE"), nullable=False
    )
    fingerprint: Mapped[str] = mapped_column(String(40), nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    finding: Mapped[Finding] = relationship(back_populates="events")
