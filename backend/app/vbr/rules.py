"""巡检规则目录。

每条规则声明自己的元数据、默认阈值与检查函数。
`param_schema` 同时被后端校验与前端「规则配置」页的自动生成表单使用 ——
新增规则时前端无需改动。
"""
from dataclasses import dataclass, field
from typing import Callable, Optional

from app.vbr import checks
from app.vbr.context import Finding, InspectionContext

#: 检查函数签名
CheckFn = Callable[[InspectionContext, dict, dict], list[Finding]]


@dataclass(frozen=True)
class RuleSpec:
    """一条巡检规则的规格。"""

    key: str
    category: str
    title: str
    description: str
    default_level: str
    #: global = 整轮一次；否则对集合中的每个实体各执行一次
    collection: Optional[str]
    fn: CheckFn
    default_params: dict = field(default_factory=dict)
    #: 阈值参数描述，供前端生成表单
    param_schema: tuple = ()

    def to_public_dict(self) -> dict:
        """导出给前端的规则元数据（不含函数引用）。"""
        return {
            "rule_key": self.key,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "default_level": self.default_level,
            "collection": self.collection,
            "default_params": dict(self.default_params),
            "param_schema": list(self.param_schema),
        }


def _p(key: str, label: str, type_: str, default, **extra) -> dict:
    """构造一个参数描述。"""
    schema = {"key": key, "label": label, "type": type_, "default": default}
    schema.update(extra)
    return schema


#: 规则目录
RULE_SPECS: tuple[RuleSpec, ...] = (
    # ------------------------------------------------------------------ 服务器
    RuleSpec(
        key="server.version",
        category="server",
        title="VBR 版本",
        description="构建号低于要求的最低版本时告警",
        default_level="warn",
        collection=None,
        fn=checks.check_server_version,
        default_params={"min_build": "13.1"},
        param_schema=(
            _p("min_build", "最低版本", "string", "13.1", placeholder="例如 13.1"),
        ),
    ),
    RuleSpec(
        key="server.patches",
        category="server",
        title="补丁状态",
        description="未安装任何补丁时提示",
        default_level="info",
        collection=None,
        fn=checks.check_server_patches,
    ),
    RuleSpec(
        key="server.registration",
        category="server",
        title="支持账户注册",
        description="VBR 未注册到支持账户时提示",
        default_level="info",
        collection=None,
        fn=checks.check_server_registration,
    ),
    RuleSpec(
        key="server.database",
        category="server",
        title="数据库信息",
        description="展示当前使用的数据库版本",
        default_level="info",
        collection=None,
        fn=checks.check_server_database,
    ),
    # -------------------------------------------------------------------- 许可
    RuleSpec(
        key="license.status",
        category="license",
        title="许可状态",
        description="许可状态不是 Valid 时告警",
        default_level="critical",
        collection=None,
        fn=checks.check_license_status,
    ),
    RuleSpec(
        key="license.instance_usage",
        category="license",
        title="许可实例用量",
        description="已用实例配额占比超过阈值时告警",
        default_level="warn",
        collection=None,
        fn=checks.check_license_instance_usage,
        default_params={"max_instance_percent": 90},
        param_schema=(
            _p("max_instance_percent", "用量上限（%）", "number", 90, min=1, max=100),
        ),
    ),
    # -------------------------------------------------------------------- 作业
    RuleSpec(
        key="job.disabled",
        category="job",
        title="作业被禁用",
        description="存在被禁用的备份作业时告警",
        default_level="warn",
        collection="jobs",
        fn=checks.check_job_disabled,
    ),
    RuleSpec(
        key="job.last_result",
        category="job",
        title="上次运行结果",
        description="上次运行结果不是 Success 时告警",
        default_level="critical",
        collection="jobs",
        fn=checks.check_job_last_result,
    ),
    RuleSpec(
        key="job.stale",
        category="job",
        title="备份时效",
        description="距上次运行超过阈值即判定长时间没有成功备份",
        default_level="critical",
        collection="jobs",
        fn=checks.check_job_stale,
        default_params={"max_age_hours": 48},
        param_schema=(
            _p("max_age_hours", "最大间隔（小时）", "number", 48, min=1),
        ),
    ),
    RuleSpec(
        key="job.not_scheduled",
        category="job",
        title="调度计划缺失",
        description="作业没有配置调度计划时告警",
        default_level="warn",
        collection="jobs",
        fn=checks.check_job_not_scheduled,
    ),
    # ------------------------------------------------------------------ 还原点
    RuleSpec(
        key="restore_point.stale",
        category="restore-point",
        title="还原点时效",
        description="受保护对象的最新还原点超过阈值未更新时告警",
        default_level="critical",
        collection="restore_points",
        fn=checks.check_restore_point_stale,
        default_params={"max_age_hours": 48},
        param_schema=(
            _p("max_age_hours", "最大间隔（小时）", "number", 48, min=1),
        ),
    ),
    RuleSpec(
        key="restore_point.malware",
        category="restore-point",
        title="恶意软件扫描",
        description="还原点恶意软件扫描状态不是 Clean 时告警",
        default_level="warn",
        collection="restore_points",
        fn=checks.check_restore_point_malware,
    ),
    # -------------------------------------------------------------------- 仓库
    RuleSpec(
        key="repo.offline",
        category="repository",
        title="仓库离线",
        description="仓库处于离线状态时告警",
        default_level="critical",
        collection="repositories",
        fn=checks.check_repo_offline,
    ),
    RuleSpec(
        key="repo.out_of_date",
        category="repository",
        title="仓库版本过期",
        description="仓库版本过期时告警",
        default_level="warn",
        collection="repositories",
        fn=checks.check_repo_out_of_date,
    ),
    RuleSpec(
        key="repo.free_space",
        category="repository",
        title="仓库剩余空间",
        description="剩余空间百分比或绝对值低于阈值时告警",
        default_level="warn",
        collection="repositories",
        fn=checks.check_repo_free_space,
        default_params={"min_free_percent": 20, "min_free_gb": 20},
        param_schema=(
            _p("min_free_percent", "剩余百分比下限（%）", "number", 20, min=0, max=100),
            _p("min_free_gb", "剩余空间下限（GB）", "number", 20, min=0),
        ),
    ),
    # -------------------------------------------------------------------- 代理
    RuleSpec(
        key="proxy.disabled",
        category="proxy",
        title="代理被禁用",
        description="存在被禁用的代理时告警",
        default_level="warn",
        collection="proxies",
        fn=checks.check_proxy_disabled,
    ),
    RuleSpec(
        key="proxy.offline",
        category="proxy",
        title="代理离线",
        description="代理处于离线状态时告警",
        default_level="critical",
        collection="proxies",
        fn=checks.check_proxy_offline,
    ),
    RuleSpec(
        key="proxy.out_of_date",
        category="proxy",
        title="代理版本过期",
        description="代理版本过期时告警",
        default_level="warn",
        collection="proxies",
        fn=checks.check_proxy_out_of_date,
    ),
    RuleSpec(
        key="proxy.online",
        category="proxy",
        title="代理在线状态",
        description="展示代理在线情况",
        default_level="ok",
        collection="proxies",
        fn=checks.check_proxy_online,
    ),
    # -------------------------------------------------------------- 受管服务器
    RuleSpec(
        key="managed_server.status",
        category="managed-server",
        title="受管服务器状态",
        description="vCenter / 受管主机状态不是 Available 时告警",
        default_level="critical",
        collection="managedServers",
        fn=checks.check_managed_server_status,
    ),
    # -------------------------------------------------------------- 受保护对象
    RuleSpec(
        key="backup_object.failed",
        category="backup-object",
        title="受保护对象备份失败",
        description="受保护对象上次备份失败时告警",
        default_level="warn",
        collection="backupObjects",
        fn=checks.check_backup_object_failed,
    ),
)

#: rule_key → RuleSpec
RULE_MAP: dict[str, RuleSpec] = {spec.key: spec for spec in RULE_SPECS}


def get_spec(rule_key: str) -> Optional[RuleSpec]:
    """按 key 取规则规格。"""
    return RULE_MAP.get(rule_key)


def catalogue() -> list[dict]:
    """导出完整规则目录（给前端与种子数据用）。"""
    return [spec.to_public_dict() for spec in RULE_SPECS]
