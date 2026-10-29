"""远程操作端点映射。

端点与请求体均已对 VBR 13.1 的 swagger 规范核实：
- POST /api/v1/jobs/{id}/start   body 必填 performActiveFull
- POST /api/v1/jobs/{id}/retry   body 可选 startChainedJobs
- POST /api/v1/backupInfrastructure/proxies/{id}/enable   无请求体
- POST /api/v1/backupInfrastructure/proxies/{id}/disable  无请求体
"""
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass(frozen=True)
class OperationSpec:
    """一种远程操作的定义。"""

    kind: str
    #: 目标标识在 params 中的键名
    id_param: str
    #: 生成 VBR 路径
    path_builder: Callable[[str], str]
    #: 生成请求体
    body_builder: Callable[[dict], Optional[dict]] = field(default=lambda params: None)
    #: 参数校验
    validate: Callable[[dict], None] = field(default=lambda params: None)
    description: str = ""


def _require(params: dict, key: str) -> str:
    value = params.get(key)
    if not value or not isinstance(value, str):
        raise ValueError(f"参数 {key} 缺失或非法")
    return value


def _job_start_body(params: dict) -> dict:
    body: dict = {"performActiveFull": bool(params.get("perform_active_full", False))}
    if params.get("start_chained_jobs") is not None:
        body["startChainedJobs"] = bool(params["start_chained_jobs"])
    return body


def _job_retry_body(params: dict) -> Optional[dict]:
    if params.get("start_chained_jobs") is None:
        return None
    return {"startChainedJobs": bool(params["start_chained_jobs"])}


OPERATION_SPECS: dict[str, OperationSpec] = {
    "job.start": OperationSpec(
        kind="job.start",
        id_param="job_id",
        path_builder=lambda job_id: f"/api/v1/jobs/{job_id}/start",
        body_builder=_job_start_body,
        validate=lambda params: _require(params, "job_id"),
        description="立即启动一次备份作业",
    ),
    "job.retry": OperationSpec(
        kind="job.retry",
        id_param="job_id",
        path_builder=lambda job_id: f"/api/v1/jobs/{job_id}/retry",
        body_builder=_job_retry_body,
        validate=lambda params: _require(params, "job_id"),
        description="重试上一次失败的作业会话",
    ),
    "proxy.enable": OperationSpec(
        kind="proxy.enable",
        id_param="proxy_id",
        path_builder=lambda proxy_id: (
            f"/api/v1/backupInfrastructure/proxies/{proxy_id}/enable"
        ),
        validate=lambda params: _require(params, "proxy_id"),
        description="启用备份代理",
    ),
    "proxy.disable": OperationSpec(
        kind="proxy.disable",
        id_param="proxy_id",
        path_builder=lambda proxy_id: (
            f"/api/v1/backupInfrastructure/proxies/{proxy_id}/disable"
        ),
        validate=lambda params: _require(params, "proxy_id"),
        description="禁用备份代理",
    ),
}


def get_spec(kind: str) -> Optional[OperationSpec]:
    """按类型取操作定义。"""
    return OPERATION_SPECS.get(kind)
