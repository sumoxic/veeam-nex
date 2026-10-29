"""指标服务：仪表盘汇总与趋势序列。

所有趋势都基于快照表（repo/job/restore_point），
发现项趋势基于只追加的 finding_events。
"""
from datetime import timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.finding import Finding, FindingEvent, FindingStatus
from app.models.inspection import (
    InspectionRun,
    JobSnapshot,
    RepoSnapshot,
    RestorePointSnapshot,
)
from app.models.target import Target
from app.utils.errors import NotFoundError
from app.utils.timeutil import parse_iso, to_utc_naive, utcnow


def _points(rows: list[dict]) -> list[dict]:
    """统一序列点结构，供前端 ECharts 直接使用。"""
    return [{"time": r["time"], "value": r["value"]} for r in rows]


def repository_free_space_trend(
    db: Session,
    target_id: int,
    repository_id: Optional[str] = None,
    days: int = 30,
) -> list[dict]:
    """仓库剩余空间百分比趋势。"""
    since = to_utc_naive(utcnow()) - timedelta(days=days)
    stmt = select(
        RepoSnapshot.observed_at,
        RepoSnapshot.repository_name,
        RepoSnapshot.free_percent,
        RepoSnapshot.free_gb,
    ).where(
        RepoSnapshot.target_id == target_id,
        RepoSnapshot.observed_at >= since,
    )
    if repository_id:
        stmt = stmt.where(RepoSnapshot.repository_id == repository_id)
    rows = db.execute(stmt.order_by(RepoSnapshot.observed_at)).all()

    grouped: dict[str, list[dict]] = {}
    for observed_at, name, percent, free_gb in rows:
        key = name or "未知仓库"
        grouped.setdefault(key, []).append(
            {
                "time": observed_at.isoformat(),
                "value": percent,
                "free_gb": free_gb,
            }
        )
    return [
        {"repository": name, "points": _points(points)} for name, points in grouped.items()
    ]


def job_last_success_trend(
    db: Session,
    target_id: int,
    job_id: Optional[str] = None,
    days: int = 30,
) -> list[dict]:
    """作业上次运行时间趋势（VBR 时钟值）。"""
    since = to_utc_naive(utcnow()) - timedelta(days=days)
    stmt = select(
        JobSnapshot.observed_at,
        JobSnapshot.job_id,
        JobSnapshot.job_name,
        JobSnapshot.last_run_at,
        JobSnapshot.last_result,
        JobSnapshot.status,
    ).where(JobSnapshot.target_id == target_id, JobSnapshot.observed_at >= since)
    if job_id:
        stmt = stmt.where(JobSnapshot.job_id == job_id)
    rows = db.execute(stmt.order_by(JobSnapshot.observed_at)).all()

    grouped: dict[str, list[dict]] = {}
    for observed_at, jid, name, last_run_at, last_result, status in rows:
        key = name or jid
        grouped.setdefault(key, []).append(
            {
                "time": observed_at.isoformat(),
                "value": last_run_at.isoformat() if last_run_at else None,
                "last_result": last_result,
                "status": status,
            }
        )
    return [
        {"job": name, "points": _points(points)} for name, points in grouped.items()
    ]


def restore_point_age_trend(
    db: Session,
    target_id: int,
    object_name: Optional[str] = None,
    days: int = 30,
) -> list[dict]:
    """还原点时效趋势（小时）。"""
    since = to_utc_naive(utcnow()) - timedelta(days=days)
    stmt = select(
        RestorePointSnapshot.observed_at,
        RestorePointSnapshot.object_name,
        RestorePointSnapshot.age_hours,
    ).where(
        RestorePointSnapshot.target_id == target_id,
        RestorePointSnapshot.observed_at >= since,
    )
    if object_name:
        stmt = stmt.where(RestorePointSnapshot.object_name == object_name)
    rows = db.execute(stmt.order_by(RestorePointSnapshot.observed_at)).all()

    grouped: dict[str, list[dict]] = {}
    for observed_at, name, age in rows:
        key = name or "未知对象"
        grouped.setdefault(key, []).append(
            {"time": observed_at.isoformat(), "value": age}
        )
    return [{"object": name, "points": _points(points)} for name, points in grouped.items()]


def findings_trend(db: Session, target_id: Optional[int] = None, days: int = 30) -> list[dict]:
    """发现项数量趋势（按级别）。"""
    since = to_utc_naive(utcnow()) - timedelta(days=days)
    stmt = select(
        func.date(FindingEvent.created_at),
        FindingEvent.level,
        func.count(FindingEvent.id),
    ).where(FindingEvent.created_at >= since)
    if target_id is not None:
        stmt = stmt.where(FindingEvent.target_id == target_id)
    rows = db.execute(stmt.group_by(func.date(FindingEvent.created_at), FindingEvent.level)).all()

    buckets: dict[str, dict] = {}
    for day, level, count in rows:
        key = day.isoformat() if hasattr(day, "isoformat") else str(day)
        bucket = buckets.setdefault(key, {"time": key, "critical": 0, "warn": 0, "info": 0})
        bucket[level] = bucket.get(level, 0) + count
    return [buckets[key] for key in sorted(buckets)]


def _latest_license(db: Session, target_id: int) -> dict:
    """从最近一次巡检的原始清单里取许可信息。"""
    run = db.scalar(
        select(InspectionRun)
        .where(InspectionRun.target_id == target_id, InspectionRun.inventory_json.is_not(None))
        .order_by(InspectionRun.started_at.desc())
        .limit(1)
    )
    if run is None:
        return {}
    license_info = (run.inventory_json or {}).get("license") or {}
    summary = license_info.get("instanceLicenseSummary") or {}
    used = summary.get("usedInstancesNumber")
    licensed = summary.get("licensedInstancesNumber")
    percent = None
    if used is not None and licensed:
        percent = used / licensed * 100
    return {
        "status": license_info.get("status"),
        "edition": license_info.get("edition"),
        "licensed_to": license_info.get("licensedTo"),
        "used_instances": used,
        "licensed_instances": licensed,
        "used_percent": percent,
        "expiration_date": summary.get("expirationDate"),
    }


def dashboard_summary(db: Session, target_id: Optional[int] = None) -> dict:
    """仪表盘汇总：目标健康、发现项分布、许可用量。"""
    targets_stmt = select(Target)
    if target_id is not None:
        targets_stmt = targets_stmt.where(Target.id == target_id)
    targets = list(db.scalars(targets_stmt.order_by(Target.id)).all())

    target_cards = []
    for target in targets:
        last_run = db.scalar(
            select(InspectionRun)
            .where(InspectionRun.target_id == target.id)
            .order_by(InspectionRun.started_at.desc())
            .limit(1)
        )
        counts = {"critical": 0, "warn": 0, "info": 0}
        for level in counts:
            counts[level] = db.scalar(
                select(func.count(Finding.id)).where(
                    Finding.target_id == target.id,
                    Finding.status != FindingStatus.RESOLVED,
                    Finding.level == level,
                )
            ) or 0
        target_cards.append(
            {
                "target": {
                    "id": target.id,
                    "name": target.name,
                    "host": target.host,
                    "is_enabled": target.is_enabled,
                    "last_run_at": target.last_run_at,
                    "last_run_status": target.last_run_status,
                },
                "last_run": {
                    "id": last_run.id,
                    "status": last_run.status.value,
                    "started_at": last_run.started_at,
                    "duration_ms": last_run.duration_ms,
                    "findings_critical": last_run.findings_critical,
                    "findings_warn": last_run.findings_warn,
                }
                if last_run
                else None,
                "open_findings": counts,
                "license": _latest_license(db, target.id),
            }
        )

    # 全局发现项分布
    level_stmt = select(Finding.level, func.count(Finding.id))
    if target_id is not None:
        level_stmt = level_stmt.where(Finding.target_id == target_id)
    level_rows = db.execute(level_stmt.group_by(Finding.level)).all()
    by_level = {level: count for level, count in level_rows}

    status_stmt = select(Finding.status, func.count(Finding.id))
    if target_id is not None:
        status_stmt = status_stmt.where(Finding.target_id == target_id)
    status_rows = db.execute(status_stmt.group_by(Finding.status)).all()
    by_status = {status.value: count for status, count in status_rows}

    run_stats = db.execute(
        select(InspectionRun.status, func.count(InspectionRun.id)).group_by(
            InspectionRun.status
        )
    ).all()

    return {
        "targets": target_cards,
        "findings_by_level": by_level,
        "findings_by_status": by_status,
        "runs_by_status": {status.value: count for status, count in run_stats},
        "total_targets": len(targets),
    }


# ---------------------------------------------------------------- 按巡检轮次


LEVEL_ORDER = {"critical": 0, "warn": 1, "info": 2}


def _run_license(inventory: dict) -> dict:
    """从指定轮次的清单里提取许可信息。"""
    info = (inventory or {}).get("license") or {}
    summary = info.get("instanceLicenseSummary") or {}
    used = summary.get("usedInstancesNumber")
    licensed = summary.get("licensedInstancesNumber")
    percent = used / licensed * 100 if used is not None and licensed else None
    return {
        "status": info.get("status"),
        "edition": info.get("edition"),
        "type": info.get("type"),
        "licensed_to": info.get("licensedTo"),
        "support_id": info.get("supportId"),
        "package": summary.get("package"),
        "used_instances": used,
        "licensed_instances": licensed,
        "used_percent": percent,
        "expiration_date": summary.get("expirationDate"),
    }


def _run_jobs(db: Session, run: InspectionRun, inventory: dict) -> list[dict]:
    """备份任务列表；清单缺失时退回快照表。"""
    configs = {c.get("id"): c for c in (inventory.get("jobConfigs") or [])}
    jobs = []
    for job in inventory.get("jobs") or []:
        progress = job.get("sessionProgress") or {}
        config = configs.get(job.get("id")) or {}
        jobs.append(
            {
                "id": job.get("id"),
                "name": job.get("name"),
                "type": job.get("type"),
                "workload": job.get("workload"),
                "status": job.get("status"),
                "last_result": job.get("lastResult"),
                "last_run_at": job.get("lastRun"),
                "next_run": job.get("nextRun"),
                "next_run_policy": job.get("nextRunPolicy"),
                "repository_name": job.get("repositoryName") or job.get("targetName"),
                "objects_count": job.get("objectsCount"),
                "progress_percent": job.get("progressPercent"),
                "session_duration": progress.get("duration"),
                "bottleneck": progress.get("bottleneck"),
                "is_disabled": bool(config.get("isDisabled")),
            }
        )
    if jobs:
        return jobs

    rows = db.scalars(select(JobSnapshot).where(JobSnapshot.run_id == run.id)).all()
    return [
        {
            "id": row.job_id,
            "name": row.job_name,
            "type": row.job_type,
            "workload": None,
            "status": row.status,
            "last_result": row.last_result,
            "last_run_at": row.last_run_at,
            "next_run": row.next_run,
            "next_run_policy": row.next_run_policy,
            "repository_name": None,
            "objects_count": row.objects_count,
            "progress_percent": row.progress_percent,
            "session_duration": None,
            "bottleneck": None,
            "is_disabled": bool(row.is_disabled),
        }
        for row in rows
    ]


def _run_repositories(db: Session, run: InspectionRun, inventory: dict) -> list[dict]:
    repos = []
    for repo in inventory.get("repositories") or []:
        capacity = repo.get("capacityGB")
        free = repo.get("freeGB")
        percent = (free / capacity * 100) if capacity and free is not None else None
        repos.append(
            {
                "id": repo.get("id"),
                "name": repo.get("name"),
                "path": repo.get("path"),
                "type": repo.get("type"),
                "host_name": repo.get("hostName"),
                "capacity_gb": capacity,
                "free_gb": free,
                "used_space_gb": repo.get("usedSpaceGB"),
                "free_percent": percent,
                "is_online": repo.get("isOnline"),
                "is_out_of_date": repo.get("isOutOfDate"),
            }
        )
    if repos:
        return repos

    rows = db.scalars(select(RepoSnapshot).where(RepoSnapshot.run_id == run.id)).all()
    return [
        {
            "id": row.repository_id,
            "name": row.repository_name,
            "path": row.repository_path,
            "type": None,
            "host_name": None,
            "capacity_gb": row.capacity_gb,
            "free_gb": row.free_gb,
            "used_space_gb": row.used_space_gb,
            "free_percent": row.free_percent,
            "is_online": row.is_online,
            "is_out_of_date": row.is_out_of_date,
        }
        for row in rows
    ]


def _run_restore_points(db: Session, run: InspectionRun, inventory: dict) -> list[dict]:
    rows = db.scalars(
        select(RestorePointSnapshot)
        .where(RestorePointSnapshot.run_id == run.id)
        .order_by(RestorePointSnapshot.id)
    ).all()
    if rows:
        return [
            {
                "id": row.restore_point_id,
                "name": row.object_name,
                "type": None,
                "creation_time": row.creation_time,
                "age_hours": row.age_hours,
                "malware_status": row.malware_status,
                "original_size": row.original_size,
            }
            for row in rows
        ]

    vbr_now = run.vbr_server_time
    items = []
    for rp in inventory.get("restorePoints") or []:
        created = parse_iso(rp.get("creationTime"))
        hours = None
        if vbr_now is not None and created is not None:
            hours = (vbr_now - to_utc_naive(created)).total_seconds() / 3600.0
        items.append(
            {
                "id": rp.get("id"),
                "name": rp.get("name"),
                "type": rp.get("type"),
                "creation_time": to_utc_naive(created) if created else None,
                "age_hours": hours,
                "malware_status": rp.get("malwareStatus"),
                "original_size": rp.get("originalSize"),
            }
        )
    return items


def _run_sessions(inventory: dict, limit: int = 8) -> list[dict]:
    items = []
    for session in inventory.get("sessions") or []:
        result = session.get("result") or {}
        items.append(
            {
                "id": session.get("id"),
                "name": session.get("name"),
                "session_type": session.get("sessionType"),
                "state": session.get("state"),
                "result": result.get("result"),
                "message": result.get("message"),
                "creation_time": session.get("creationTime"),
                "end_time": session.get("endTime"),
                "progress_percent": session.get("progressPercent"),
                "initiated_by": session.get("initiatedBy"),
            }
        )

    def sort_key(item: dict) -> float:
        parsed = parse_iso(item.get("creation_time"))
        return parsed.timestamp() if parsed else 0.0

    items.sort(key=sort_key, reverse=True)
    return items[:limit]


def recent_runs(db: Session, limit: int = 40) -> list[dict]:
    """近期巡检轮次，供仪表盘选择时间使用。"""
    rows = db.execute(
        select(InspectionRun, Target.name)
        .join(Target, Target.id == InspectionRun.target_id)
        .order_by(InspectionRun.started_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": run.id,
            "target_id": run.target_id,
            "target_name": target_name,
            "status": run.status.value,
            "trigger_type": run.trigger_type.value,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "duration_ms": run.duration_ms,
            "findings_total": run.findings_total,
            "findings_critical": run.findings_critical,
            "findings_warn": run.findings_warn,
            "findings_info": run.findings_info,
            "error_count": run.error_count,
        }
        for run, target_name in rows
    ]


def run_dashboard(db: Session, run_id: int) -> dict:
    """一轮巡检对应的仪表盘数据。

    数值全部来自该轮巡检落库的原始清单（缺失时退回快照表），
    因此切换巡检时间看到的是当时 VBR 的真实状态，而不是当前状态。
    """
    run = db.get(InspectionRun, run_id)
    if run is None:
        raise NotFoundError(f"巡检运行记录 {run_id} 不存在")
    target = db.get(Target, run.target_id)
    if target is None:
        raise NotFoundError(f"巡检目标 {run.target_id} 不存在")

    inventory = run.inventory_json or {}
    jobs = _run_jobs(db, run, inventory)
    repositories = _run_repositories(db, run, inventory)
    restore_points = _run_restore_points(db, run, inventory)

    job_stats = {
        "total": len(jobs),
        "success": 0,
        "warning": 0,
        "failed": 0,
        "running": 0,
        "disabled": 0,
        "unknown": 0,
    }
    for job in jobs:
        result = (job.get("last_result") or "").lower()
        if result in ("success", "warning", "failed"):
            job_stats[result] += 1
        else:
            job_stats["unknown"] += 1
        if (job.get("status") or "").lower() == "running":
            job_stats["running"] += 1
        if job.get("is_disabled"):
            job_stats["disabled"] += 1

    capacity = sum(r["capacity_gb"] for r in repositories if r.get("capacity_gb"))
    free = sum(r["free_gb"] for r in repositories if r.get("free_gb") is not None)
    repo_stats = {
        "total": len(repositories),
        "online": sum(1 for r in repositories if r.get("is_online")),
        "capacity_gb": capacity,
        "free_gb": free,
        "used_gb": max(capacity - free, 0.0) if capacity else 0.0,
        "free_percent": (free / capacity * 100) if capacity else None,
    }

    ages = [rp["age_hours"] for rp in restore_points if rp.get("age_hours") is not None]
    malware = {"clean": 0, "warning": 0, "unknown": 0}
    for rp in restore_points:
        status = (rp.get("malware_status") or "").lower()
        if status == "clean":
            malware["clean"] += 1
        elif status in ("warning", "infected", "suspicious"):
            malware["warning"] += 1
        else:
            malware["unknown"] += 1

    objects = []
    for obj in inventory.get("backupObjects") or []:
        objects.append(
            {
                "id": obj.get("id"),
                "name": obj.get("name"),
                "path": obj.get("path"),
                "size": obj.get("size"),
                "type": obj.get("type"),
                "last_run_failed": obj.get("lastRunFailed"),
                "restore_points_count": obj.get("restorePointsCount"),
            }
        )
    objects.sort(key=lambda item: item.get("size") or 0, reverse=True)

    proxies = [
        {
            "id": proxy.get("id"),
            "name": proxy.get("name"),
            "type": proxy.get("type"),
            "host_name": proxy.get("hostName"),
            "is_online": proxy.get("isOnline"),
            "is_disabled": proxy.get("isDisabled"),
            "is_out_of_date": proxy.get("isOutOfDate"),
        }
        for proxy in inventory.get("proxies") or []
    ]
    managed_servers = [
        {
            "id": server.get("id"),
            "name": server.get("name"),
            "type": server.get("type"),
            "status": server.get("status"),
            "vi_host_type": server.get("viHostType"),
            "is_backup_server": server.get("isBackupServer"),
            "description": server.get("description"),
        }
        for server in inventory.get("managedServers") or []
    ]
    services = [
        {"name": service.get("name"), "port": service.get("port")}
        for service in inventory.get("services") or []
    ]

    finding_rows = db.scalars(
        select(Finding).where(Finding.last_run_id == run.id)
    ).all()
    findings = sorted(
        [
            {
                "id": row.id,
                "level": row.level,
                "rule_key": row.rule_key,
                "category": row.category,
                "subject": row.subject,
                "message": row.message,
                "status": row.status.value,
                "last_seen_at": row.last_seen_at,
            }
            for row in finding_rows
        ],
        key=lambda item: (LEVEL_ORDER.get(item["level"], 9), item["id"]),
    )
    findings_by_level = {"critical": 0, "warn": 0, "info": 0}
    for item in findings:
        if item["level"] in findings_by_level:
            findings_by_level[item["level"]] += 1

    server = inventory.get("server") or {}
    return {
        "run": {
            "id": run.id,
            "target_id": run.target_id,
            "status": run.status.value,
            "trigger_type": run.trigger_type.value,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "duration_ms": run.duration_ms,
            "clock_source": run.clock_source.value,
            "vbr_server_time": run.vbr_server_time,
            "vbr_build": run.vbr_build,
            "findings_total": run.findings_total,
            "findings_critical": run.findings_critical,
            "findings_warn": run.findings_warn,
            "findings_info": run.findings_info,
            "error_count": run.error_count,
            "error_message": run.error_message,
        },
        "target": {
            "id": target.id,
            "name": target.name,
            "host": target.host,
            "is_enabled": target.is_enabled,
        },
        "server": {
            "name": server.get("name"),
            "build_version": server.get("buildVersion"),
            "platform": server.get("platform"),
            "database_vendor": server.get("databaseVendor"),
            "database_version": server.get("sqlServerVersion"),
            "database_schema_version": server.get("databaseSchemaVersion"),
        },
        "license": _run_license(inventory),
        "jobs": jobs,
        "job_stats": job_stats,
        "repositories": repositories,
        "repo_stats": repo_stats,
        "restore_points": {
            "total": len(restore_points),
            "avg_age_hours": (sum(ages) / len(ages)) if ages else None,
            "max_age_hours": max(ages) if ages else None,
            "clean": malware["clean"],
            "warning": malware["warning"],
            "unknown": malware["unknown"],
            "items": restore_points[:20],
        },
        "backup_objects": {
            "total": len(objects),
            "total_size": sum(item.get("size") or 0 for item in objects),
            "failed": sum(1 for item in objects if item.get("last_run_failed")),
            "items": objects[:20],
        },
        "proxies": proxies,
        "managed_servers": managed_servers,
        "services": services,
        "sessions": _run_sessions(inventory),
        "findings": findings,
        "findings_by_level": findings_by_level,
    }
