"""VBR 端点清单。

COLLECT_ENDPOINTS —— 巡检采集用到的端点；
INSPECTION_ENDPOINTS —— 能力探测用的端点全集。
"""
from typing import NamedTuple


class CollectEndpoint(NamedTuple):
    """一个参与采集的端点。"""

    #: 采集结果在 inventory 中的键名
    key: str
    path: str
    #: 是否为列表端点（需要翻页）
    is_list: bool
    #: 主端点：失败会判定整轮巡检失败；次端点失败只记 error 条目
    primary: bool = True


#: 巡检采集端点清单
COLLECT_ENDPOINTS: tuple[CollectEndpoint, ...] = (
    CollectEndpoint("server", "/api/v1/serverInfo", is_list=False),
    CollectEndpoint("license", "/api/v1/license", is_list=False),
    CollectEndpoint("serverTime", "/api/v1/serverTime", is_list=False),
    CollectEndpoint("jobs", "/api/v1/jobs/states", is_list=True),
    CollectEndpoint("jobConfigs", "/api/v1/jobs", is_list=True),
    CollectEndpoint("taskSessions", "/api/v1/taskSessions", is_list=True),
    CollectEndpoint("restorePoints", "/api/v1/restorePoints", is_list=True),
    CollectEndpoint(
        "repositories",
        "/api/v1/backupInfrastructure/repositories/states",
        is_list=True,
    ),
    CollectEndpoint(
        "proxies", "/api/v1/backupInfrastructure/proxies/states", is_list=True
    ),
    CollectEndpoint(
        "managedServers", "/api/v1/backupInfrastructure/managedServers", is_list=True
    ),
    CollectEndpoint("backupObjects", "/api/v1/backupObjects", is_list=True, primary=False),
    CollectEndpoint("sessions", "/api/v1/sessions", is_list=True, primary=False),
    CollectEndpoint("services", "/api/v1/services", is_list=True, primary=False),
)

#: 能力探测端点：路径 → 该端点能提供什么
INSPECTION_ENDPOINTS: dict[str, str] = {
    "/api/v1/serverInfo": "服务器版本、构建号、补丁、数据库",
    "/api/v1/license": "许可状态、实例用量、受保护负载",
    "/api/v1/serverTime": "VBR 服务器时钟与时区",
    "/api/v1/jobs/states": "作业状态、上次结果、上次运行、下次运行、进度",
    "/api/v1/jobs": "作业调度、启用状态、受保护对象",
    "/api/v1/taskSessions": "运行历史与传输统计",
    "/api/v1/restorePoints": "各对象的还原点",
    "/api/v1/backupObjects": "受保护对象及其备份",
    "/api/v1/backupInfrastructure/repositories/states": "仓库剩余空间与在线状态",
    "/api/v1/backupInfrastructure/proxies/states": "代理在线与禁用状态",
    "/api/v1/backupInfrastructure/managedServers": "vCenter / 受管主机状态",
    "/api/v1/sessions": "正在运行的会话",
    "/api/v1/services": "Windows 服务状态",
    "/api/v1/authorization/events": "审计与授权事件",
    "/api/v1/license/capacity": "许可容量报告",
}

#: VBR 13 才有的代理状态端点；VBR 12 只能读代理配置列表
PROXY_STATES_PATH = "/api/v1/backupInfrastructure/proxies/states"
PROXY_CONFIG_PATH = "/api/v1/backupInfrastructure/proxies"


def _is_v13(api_version: str) -> bool:
    return api_version.startswith("1.3")


def collect_endpoints(api_version: str) -> tuple[CollectEndpoint, ...]:
    """按 REST API 版本返回采集端点清单。"""
    proxy_path = PROXY_STATES_PATH if _is_v13(api_version) else PROXY_CONFIG_PATH
    return tuple(
        endpoint._replace(path=proxy_path) if endpoint.key == "proxies" else endpoint
        for endpoint in COLLECT_ENDPOINTS
    )


def inspection_endpoints(api_version: str) -> dict[str, str]:
    """按 REST API 版本返回能力探测端点及说明。"""
    if _is_v13(api_version):
        return dict(INSPECTION_ENDPOINTS)
    result: dict[str, str] = {}
    for path, desc in INSPECTION_ENDPOINTS.items():
        if path == PROXY_STATES_PATH:
            result[PROXY_CONFIG_PATH] = (
                "代理配置（VBR 12 无 states 端点，在线状态由受管服务器推断）"
            )
        else:
            result[path] = desc
    return result
