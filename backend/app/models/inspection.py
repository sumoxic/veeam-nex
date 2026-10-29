"""巡检运行记录与趋势快照。"""
import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UTCDateTime


class RunTrigger(str, enum.Enum):
    """巡检触发来源。"""

    SCHEDULE = "schedule"
    MANUAL = "manual"
    API = "api"


class RunStatus(str, enum.Enum):
    """巡检运行状态。

    partial —— 部分端点采集失败但主流程完成
    """

    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class ClockSource(str, enum.Enum):
    """本轮巡检使用的时间基准。

    vbr —— 使用 VBR 服务器自身时钟（默认，最可靠）
    platform —— VBR 时钟获取失败，退回平台时钟，该轮标记降级
    """

    VBR = "vbr"
    PLATFORM = "platform"


class InspectionRun(Base):
    """一次巡检运行。"""

    __tablename__ = "inspection_runs"
    __table_args__ = (
        Index("idx_runs_target_time", "target_id", "started_at"),
        Index("idx_runs_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("targets.id", ondelete="CASCADE"), nullable=False
    )
    trigger_type: Mapped[RunTrigger] = mapped_column(
        Enum(RunTrigger, values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=RunStatus.RUNNING,
    )
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    clock_source: Mapped[ClockSource] = mapped_column(
        Enum(ClockSource, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=ClockSource.VBR,
    )
    #: VBR 服务器自身时间（本轮所有时长计算基准）
    vbr_server_time: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    vbr_build: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    findings_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    findings_critical: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    findings_warn: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    findings_info: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    #: 原始采集结果（裁剪到 1MB 以内）
    inventory_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class RepoSnapshot(Base):
    """仓库容量快照，用于容量趋势分析。"""

    __tablename__ = "repo_snapshots"
    __table_args__ = (
        Index("idx_repo_trend", "target_id", "repository_id", "observed_at"),
        Index("idx_repo_run", "run_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("targets.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("inspection_runs.id", ondelete="CASCADE"), nullable=False
    )
    repository_id: Mapped[str] = mapped_column(String(64), nullable=False)
    repository_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    repository_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    capacity_gb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    free_gb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    used_space_gb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    free_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_online: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    is_out_of_date: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class JobSnapshot(Base):
    """作业运行状态快照，用于「上次成功备份时间」趋势分析。

    注意：last_run_at 与 next_run 是 **VBR 时钟** 的值，与平台 UTC 时间不同源，
    不可与 observed_at 直接相减。
    """

    __tablename__ = "job_snapshots"
    __table_args__ = (
        Index("idx_job_trend", "target_id", "job_id", "observed_at"),
        Index("idx_job_run", "run_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("targets.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("inspection_runs.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[str] = mapped_column(String(64), nullable=False)
    job_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    job_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    last_result: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    next_run: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    next_run_policy: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_disabled: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    objects_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    progress_percent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class RestorePointSnapshot(Base):
    """还原点快照，用于还原点时效趋势分析。

    creation_time 是 **VBR 时钟** 的值；age_hours 已按 VBR 时钟算好并落库，
    避免后续查询时混用两套时钟。
    """

    __tablename__ = "restore_point_snapshots"
    __table_args__ = (
        Index("idx_rp_trend", "target_id", "object_name", "observed_at"),
        Index("idx_rp_run", "run_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("targets.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("inspection_runs.id", ondelete="CASCADE"), nullable=False
    )
    object_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    object_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    restore_point_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    creation_time: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    age_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    malware_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    #: 还原点原始大小（字节）。VBR 上报的是字节数，会超过 32 位整型上限
    original_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    gfs_periods: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
