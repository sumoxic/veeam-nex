"""巡检规则实现。

每个函数检查一类问题，签名为 (ctx, params, entity) → list[Finding]。
函数体沿用原 inspection.py 的判断逻辑，只是阈值改为从 params 读取，
从而支持按规则、按目标分别配置。
"""
from typing import Optional

from app.utils.timeutil import parse_iso
from app.vbr.context import Finding, InspectionContext


# --------------------------------------------------------------------- 服务器


def check_server_version(ctx: InspectionContext, params: dict, entity: dict) -> list[Finding]:
    """VBR 构建号低于要求的最低版本。"""
    server = ctx.server()
    build = server.get("buildVersion") or ""
    minimum = str(params.get("min_build", "13.1"))
    parts = build.split(".")
    try:
        current = (int(parts[0]), int(parts[1]))
        wanted = (int(minimum.split(".")[0]), int(minimum.split(".")[1]))
    except (ValueError, IndexError):
        return []
    if current < wanted:
        return [
            Finding(
                rule_key="server.version",
                category="server",
                level=ctx.level("server.version", "warn"),
                subject="version",
                subject_key="server:version",
                message=f"VBR 构建号 {build} 低于要求的 {minimum}",
            )
        ]
    return []


def check_server_patches(ctx: InspectionContext, params: dict, entity: dict) -> list[Finding]:
    """未安装任何补丁。"""
    server = ctx.server()
    if server.get("patches") is not None and not server.get("patches"):
        return [
            Finding(
                rule_key="server.patches",
                category="server",
                level=ctx.level("server.patches", "info"),
                subject="patches",
                subject_key="server:patches",
                message="未安装任何补丁",
            )
        ]
    return []


def check_server_registration(ctx: InspectionContext, params: dict, entity: dict) -> list[Finding]:
    """VBR 未注册到支持账户。"""
    registration = ctx.server().get("veeamRegistration") or {}
    if registration.get("isRegistered") is False:
        return [
            Finding(
                rule_key="server.registration",
                category="server",
                level=ctx.level("server.registration", "info"),
                subject="registration",
                subject_key="server:registration",
                message="VBR 未注册到支持账户",
            )
        ]
    return []


def check_server_database(ctx: InspectionContext, params: dict, entity: dict) -> list[Finding]:
    """数据库信息（正常状态，仅用于展示）。"""
    server = ctx.server()
    db = server.get("sqlServerVersion")
    if not db:
        return []
    return [
        Finding(
            rule_key="server.database",
            category="server",
            level=ctx.level("server.database", "info"),
            subject="database",
            subject_key="server:database",
            message=f"数据库: {db}",
        )
    ]


# ----------------------------------------------------------------------- 许可


def check_license_status(ctx: InspectionContext, params: dict, entity: dict) -> list[Finding]:
    """许可状态非 Valid。"""
    lic = ctx.license()
    status = lic.get("status")
    if not status:
        return []
    if str(status).lower() != "valid":
        return [
            Finding(
                rule_key="license.status",
                category="license",
                level=ctx.level("license.status", "critical"),
                subject="status",
                subject_key="license:status",
                message=f"许可状态为 {status}",
            )
        ]
    return [
        Finding(
            rule_key="license.status",
            category="license",
            level="ok",
            subject="status",
            subject_key="license:status",
            message=f"许可 {lic.get('edition')} / {lic.get('type')} 状态为 {status}",
        )
    ]


def check_license_instance_usage(ctx: InspectionContext, params: dict, entity: dict) -> list[Finding]:
    """许可实例配额使用率过高。"""
    lic = ctx.license()
    summary = lic.get("instanceLicenseSummary") or {}
    licensed = summary.get("licensedInstancesNumber") or 0
    used = summary.get("usedInstancesNumber") or 0
    if not licensed:
        return []
    percent = used / licensed * 100
    max_percent = float(params.get("max_instance_percent", 90))
    level = "warn" if percent >= max_percent else "ok"
    return [
        Finding(
            rule_key="license.instance_usage",
            category="license",
            level=ctx.level("license.instance_usage", "warn") if level == "warn" else "ok",
            subject="instance-usage",
            subject_key="license:instance-usage",
            message=f"已使用 {used:g}/{licensed:g} 个实例配额 ({percent:.1f}%)",
            metric_value=percent,
            threshold_value=max_percent,
        )
    ]


# ------------------------------------------------------------------------ 作业


def check_job_disabled(ctx: InspectionContext, params: dict, entity: dict) -> list[Finding]:
    """作业被禁用。"""
    if not entity.get("isDisabled"):
        return []
    name = entity.get("name") or entity.get("id")
    return [
        Finding(
            rule_key="job.disabled",
            category="job",
            level=ctx.level("job.disabled", "warn"),
            subject=name,
            subject_key=f"job:{entity.get('id')}",
            message="作业已被禁用",
        )
    ]


def check_job_last_result(ctx: InspectionContext, params: dict, entity: dict) -> list[Finding]:
    """上次运行结果不是成功。"""
    result = entity.get("lastResult")
    if not result:
        return []
    name = entity.get("name") or entity.get("id")
    if str(result).lower() != "success":
        return [
            Finding(
                rule_key="job.last_result",
                category="job",
                level=ctx.level("job.last_result", "critical"),
                subject=name,
                subject_key=f"job:{entity.get('id')}",
                message=f"上次运行结果为 {result}",
            )
        ]
    return [
        Finding(
            rule_key="job.last_result",
            category="job",
            level="ok",
            subject=name,
            subject_key=f"job:{entity.get('id')}",
            message=f"上次运行结果为 {result}",
        )
    ]


def check_job_stale(ctx: InspectionContext, params: dict, entity: dict) -> list[Finding]:
    """距上次运行超过阈值，即长时间没有成功备份。"""
    last_run = parse_iso(entity.get("lastRun"))
    if last_run is None:
        return []
    max_age = float(params.get("max_age_hours", 48))
    age = (ctx.now - last_run).total_seconds() / 3600
    if age <= max_age:
        return []
    name = entity.get("name") or entity.get("id")
    return [
        Finding(
            rule_key="job.stale",
            category="job",
            level=ctx.level("job.stale", "critical"),
            subject=name,
            subject_key=f"job:{entity.get('id')}",
            message=f"已 {age:.1f} 小时没有成功备份（上次运行 {entity.get('lastRun')}）",
            metric_value=age,
            threshold_value=max_age,
        )
    ]


def check_job_not_scheduled(ctx: InspectionContext, params: dict, entity: dict) -> list[Finding]:
    """作业没有配置调度计划。"""
    policy = entity.get("nextRunPolicy")
    if policy not in ("<Not scheduled>", "", None):
        return []
    name = entity.get("name") or entity.get("id")
    return [
        Finding(
            rule_key="job.not_scheduled",
            category="job",
            level=ctx.level("job.not_scheduled", "warn"),
            subject=name,
            subject_key=f"job:{entity.get('id')}",
            message=f"调度计划为 {policy or '未设置'}",
        )
    ]


# --------------------------------------------------------------------- 还原点


def check_restore_point_stale(ctx: InspectionContext, params: dict, entity: dict) -> list[Finding]:
    """受保护对象的最新还原点已过期。"""
    rp = entity.get("restore_point") or {}
    created = parse_iso(rp.get("creationTime"))
    if created is None:
        return []
    max_age = float(params.get("max_age_hours", 48))
    age = (ctx.now - created).total_seconds() / 3600
    name = entity.get("name")
    if age <= max_age:
        return [
            Finding(
                rule_key="restore_point.stale",
                category="restore-point",
                level="ok",
                subject=name,
                subject_key=f"restore-point:{name}",
                message=(
                    f"最新还原点距今 {age:.1f} 小时，类型 {rp.get('type')}，"
                    f"大小 {rp.get('originalSize')}"
                ),
                metric_value=age,
                threshold_value=max_age,
            )
        ]
    return [
        Finding(
            rule_key="restore_point.stale",
            category="restore-point",
            level=ctx.level("restore_point.stale", "critical"),
            subject=name,
            subject_key=f"restore-point:{name}",
            message=f"最新还原点已 {age:.1f} 小时未更新（{rp.get('creationTime')}）",
            metric_value=age,
            threshold_value=max_age,
        )
    ]


def check_restore_point_malware(ctx: InspectionContext, params: dict, entity: dict) -> list[Finding]:
    """还原点恶意软件扫描状态异常。"""
    rp = entity.get("restore_point") or {}
    status = rp.get("malwareStatus")
    if not status:
        return []
    name = entity.get("name")
    if str(status).lower() == "clean":
        return [
            Finding(
                rule_key="restore_point.malware",
                category="restore-point",
                level="ok",
                subject=name,
                subject_key=f"restore-point:{name}",
                message="恶意软件扫描状态为 clean",
            )
        ]
    return [
        Finding(
            rule_key="restore_point.malware",
            category="restore-point",
            level=ctx.level("restore_point.malware", "warn"),
            subject=name,
            subject_key=f"restore-point:{name}",
            message=f"恶意软件扫描状态为 {status}",
        )
    ]


# ------------------------------------------------------------------------ 仓库


def check_repo_offline(ctx: InspectionContext, params: dict, entity: dict) -> list[Finding]:
    """仓库离线。"""
    if entity.get("isOnline", True):
        return []
    name = entity.get("name") or entity.get("id")
    return [
        Finding(
            rule_key="repo.offline",
            category="repository",
            level=ctx.level("repo.offline", "critical"),
            subject=name,
            subject_key=f"repo:{entity.get('id')}",
            message="仓库处于离线状态",
        )
    ]


def check_repo_out_of_date(ctx: InspectionContext, params: dict, entity: dict) -> list[Finding]:
    """仓库版本过期。"""
    if not entity.get("isOutOfDate"):
        return []
    name = entity.get("name") or entity.get("id")
    return [
        Finding(
            rule_key="repo.out_of_date",
            category="repository",
            level=ctx.level("repo.out_of_date", "warn"),
            subject=name,
            subject_key=f"repo:{entity.get('id')}",
            message="仓库版本已过期",
        )
    ]


def check_repo_free_space(ctx: InspectionContext, params: dict, entity: dict) -> list[Finding]:
    """仓库剩余空间低于阈值（百分比与绝对值双阈值）。"""
    capacity = entity.get("capacityGB")
    free = entity.get("freeGB")
    if not capacity or free is None:
        return []
    percent = free / capacity * 100
    min_percent = float(params.get("min_free_percent", 20))
    min_gb = float(params.get("min_free_gb", 20))
    name = entity.get("name") or entity.get("id")
    breached = percent < min_percent or free < min_gb
    message = f"{entity.get('path')} 剩余 {free:g}GB / 共 {capacity:g}GB ({percent:.1f}%)"
    if not breached:
        return [
            Finding(
                rule_key="repo.free_space",
                category="repository",
                level="ok",
                subject=name,
                subject_key=f"repo:{entity.get('id')}",
                message=message,
                metric_value=percent,
                threshold_value=min_percent,
            )
        ]
    return [
        Finding(
            rule_key="repo.free_space",
            category="repository",
            level=ctx.level("repo.free_space", "warn"),
            subject=name,
            subject_key=f"repo:{entity.get('id')}",
            message=f"{message}，低于阈值 {min_percent:g}% / {min_gb:g}GB",
            metric_value=percent,
            threshold_value=min_percent,
        )
    ]


# ------------------------------------------------------------------------ 代理


def check_proxy_disabled(ctx: InspectionContext, params: dict, entity: dict) -> list[Finding]:
    """代理被禁用。"""
    if not entity.get("isDisabled"):
        return []
    name = entity.get("name") or entity.get("id")
    return [
        Finding(
            rule_key="proxy.disabled",
            category="proxy",
            level=ctx.level("proxy.disabled", "warn"),
            subject=name,
            subject_key=f"proxy:{entity.get('id')}",
            message="代理已被禁用",
        )
    ]


def check_proxy_offline(ctx: InspectionContext, params: dict, entity: dict) -> list[Finding]:
    """代理离线。"""
    if entity.get("isOnline", True):
        return []
    name = entity.get("name") or entity.get("id")
    return [
        Finding(
            rule_key="proxy.offline",
            category="proxy",
            level=ctx.level("proxy.offline", "critical"),
            subject=name,
            subject_key=f"proxy:{entity.get('id')}",
            message="代理处于离线状态",
        )
    ]


def check_proxy_out_of_date(ctx: InspectionContext, params: dict, entity: dict) -> list[Finding]:
    """代理版本过期。"""
    if not entity.get("isOutOfDate"):
        return []
    name = entity.get("name") or entity.get("id")
    return [
        Finding(
            rule_key="proxy.out_of_date",
            category="proxy",
            level=ctx.level("proxy.out_of_date", "warn"),
            subject=name,
            subject_key=f"proxy:{entity.get('id')}",
            message="代理版本已过期",
        )
    ]


def check_proxy_online(ctx: InspectionContext, params: dict, entity: dict) -> list[Finding]:
    """代理在线（正常状态，仅用于展示）。"""
    if not entity.get("isOnline") or entity.get("isDisabled"):
        return []
    name = entity.get("name") or entity.get("id")
    return [
        Finding(
            rule_key="proxy.online",
            category="proxy",
            level="ok",
            subject=name,
            subject_key=f"proxy:{entity.get('id')}",
            message=f"在线，类型 {entity.get('type')}",
        )
    ]


# ------------------------------------------------------------------ 受管服务器


def check_managed_server_status(ctx: InspectionContext, params: dict, entity: dict) -> list[Finding]:
    """vCenter / 受管主机状态异常。"""
    status = entity.get("status")
    if not status:
        return []
    name = entity.get("name") or entity.get("id")
    if str(status).lower() not in ("available", "connected"):
        return [
            Finding(
                rule_key="managed_server.status",
                category="managed-server",
                level=ctx.level("managed_server.status", "critical"),
                subject=name,
                subject_key=f"managed-server:{entity.get('id')}",
                message=f"受管服务器状态为 {status}",
            )
        ]
    return [
        Finding(
            rule_key="managed_server.status",
            category="managed-server",
            level="ok",
            subject=name,
            subject_key=f"managed-server:{entity.get('id')}",
            message=f"{entity.get('type')} {name} 状态为 {status}",
        )
    ]


def check_backup_object_failed(ctx: InspectionContext, params: dict, entity: dict) -> list[Finding]:
    """受保护对象上次备份失败。"""
    if not entity.get("lastRunFailed"):
        return []
    name = entity.get("name") or entity.get("id")
    return [
        Finding(
            rule_key="backup_object.failed",
            category="backup-object",
            level=ctx.level("backup_object.failed", "warn"),
            subject=name,
            subject_key=f"backup-object:{entity.get('id')}",
            message="该受保护对象上次备份失败",
        )
    ]
