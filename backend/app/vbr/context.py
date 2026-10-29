"""巡检执行上下文。

Context 承载一次巡检的全部输入：采集到的清单、当前生效的规则配置，
以及本轮的时间基准（优先使用 VBR 服务器自身时钟）。
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Optional

#: 级别严重度排序，用于告警规则比较
LEVEL_ORDER = {"ok": 0, "info": 1, "warn": 2, "critical": 3}


@dataclass
class Finding:
    """一条巡检结果。"""

    rule_key: str
    category: str
    level: str
    subject: str
    #: 机器可读的对象标识，如 "job:<uuid>"；用于生成稳定指纹
    subject_key: str
    message: str
    metric_value: Optional[float] = None
    threshold_value: Optional[float] = None

    @property
    def is_actionable(self) -> bool:
        """ok 级只计数，不落 findings 表。"""
        return self.level != "ok"


@dataclass
class RuleConfig:
    """单条规则的生效配置。"""

    enabled: bool = True
    level: Optional[str] = None
    params: dict = field(default_factory=dict)


@dataclass
class InspectionContext:
    """一次巡检的执行上下文。"""

    inventory: dict
    #: 本轮的时间基准 —— 正常情况下是 VBR 服务器时钟
    now: datetime
    #: "vbr" 或 "platform"；后者表示 VBR 时钟获取失败，该轮降级
    clock_source: str = "vbr"
    #: rule_key → RuleConfig
    config: dict[str, RuleConfig] = field(default_factory=dict)
    #: 归一化后的实体缓存
    _jobs: Optional[list[dict]] = None
    _restore_objects: Optional[list[dict]] = None

    # ------------------------------------------------------------ 规则配置

    def level(self, rule_key: str, default: str = "warn") -> str:
        """取规则生效级别，未配置时用规则规格的默认值。"""
        cfg = self.config.get(rule_key)
        if cfg and cfg.level:
            return cfg.level
        return default

    def params(self, rule_key: str) -> dict:
        """取规则生效参数。"""
        cfg = self.config.get(rule_key)
        return dict(cfg.params) if cfg else {}

    # -------------------------------------------------------------- 实体

    def jobs(self) -> list[dict]:
        """合并作业状态与作业配置的作业列表。

        /api/v1/jobs/states 提供运行状态，/api/v1/jobs 提供 isDisabled，
        两者用 id 关联。
        """
        if self._jobs is not None:
            return self._jobs
        states = self.inventory.get("jobs") or []
        configs = {
            cfg.get("id"): cfg for cfg in (self.inventory.get("jobConfigs") or [])
        }
        merged: list[dict] = []
        for state in states:
            job = dict(state)
            job["isDisabled"] = bool(configs.get(job.get("id"), {}).get("isDisabled"))
            merged.append(job)
        # 只有配置没有状态的作业也要纳入（例如刚创建还没跑过）
        known = {job.get("id") for job in merged}
        for job_id, cfg in configs.items():
            if job_id not in known:
                merged.append(
                    {
                        "id": job_id,
                        "name": cfg.get("name"),
                        "type": cfg.get("type"),
                        "isDisabled": bool(cfg.get("isDisabled")),
                        "lastResult": None,
                        "lastRun": None,
                        "nextRunPolicy": None,
                        "status": None,
                    }
                )
        self._jobs = merged
        return merged

    def restore_point_objects(self) -> list[dict]:
        """每个受保护对象的最新还原点。

        VBR 的还原点列表包含同一对象的多条记录，这里按对象名取最新的一条，
        还原点时效与恶意软件状态都以此为准。
        """
        if self._restore_objects is not None:
            return self._restore_objects
        latest: dict[str, dict] = {}
        for rp in self.inventory.get("restorePoints") or []:
            key = rp.get("name") or rp.get("id")
            if key is None:
                continue
            current = latest.get(key)
            if current is None or self._is_newer(rp, current):
                latest[key] = rp
        self._restore_objects = [
            {"name": key, "restore_point": rp} for key, rp in latest.items()
        ]
        return self._restore_objects

    def _is_newer(self, candidate: dict, current: dict) -> bool:
        """判断候选还原点是否更新。"""
        from app.utils.timeutil import parse_iso

        c_ts = parse_iso(candidate.get("creationTime"))
        cur_ts = parse_iso(current.get("creationTime"))
        if c_ts is None:
            return False
        if cur_ts is None:
            return True
        return c_ts > cur_ts

    # ------------------------------------------------------------ 便捷访问

    def collection(self, name: str) -> list[dict]:
        """取清单中的某个集合。"""
        value = self.inventory.get(name)
        return value if isinstance(value, list) else []

    def server(self) -> dict:
        value = self.inventory.get("server")
        return value if isinstance(value, dict) else {}

    def license(self) -> dict:
        value = self.inventory.get("license")
        return value if isinstance(value, dict) else {}


def level_at_least(level: str, minimum: str) -> bool:
    """判断级别是否不低于给定的最低级别。"""
    return LEVEL_ORDER.get(level, 0) >= LEVEL_ORDER.get(minimum, 0)


def iter_entities(ctx: InspectionContext, collection: str) -> Iterable[dict]:
    """按集合名产出实体，供规则函数遍历。"""
    if collection == "jobs":
        return ctx.jobs()
    if collection == "restore_points":
        return ctx.restore_point_objects()
    return ctx.collection(collection)
