"""VBR 数据采集。

只负责把数据从 VBR 取回来，不做任何策略判断。
关键约定：
1. 先读 /api/v1/serverTime，后续所有时长计算都基于 VBR 自己的时钟；
2. 认证失败（AuthError）直接向上抛，绝不吞成「空清单」；
3. 列表端点翻页取全，超出硬上限时记 error 而不是静默截断。
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.utils.timeutil import parse_iso, utcnow
from app.vbr.client import VbrClient
from app.vbr.endpoints import collect_endpoints
from app.vbr.exceptions import AuthError, LicenseRestricted, NotFound, PagingOverflow, VbrError
from app.vbr.paging import iter_all


@dataclass
class CollectionResult:
    """一次采集的结果。"""

    inventory: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    #: 本轮时间基准
    now: datetime = field(default_factory=utcnow)
    #: "vbr" 或 "platform"
    clock_source: str = "platform"
    #: 主端点是否全部成功
    degraded: bool = False

    @property
    def server_build(self) -> Optional[str]:
        server = self.inventory.get("server") or {}
        return server.get("buildVersion")


def _normalize_proxies(inventory: dict) -> None:
    """把 VBR 12 的代理配置列表补齐成与 13 相近的结构。

    VBR 12 没有 `/proxies/states`，列表项是嵌套的配置对象，不含在线状态；
    用受管服务器（hostId 对应）的 status 推断 isOnline，避免界面误显示离线。
    """
    proxies = inventory.get("proxies")
    if not isinstance(proxies, list):
        return
    servers = {
        server.get("id"): server for server in (inventory.get("managedServers") or [])
    }
    normalized: list[dict] = []
    for proxy in proxies:
        server = proxy.get("server")
        if not isinstance(server, dict) or "isOnline" in proxy:
            normalized.append(proxy)
            continue
        host_id = server.get("hostId")
        host = servers.get(host_id) or {}
        item = dict(proxy)
        item["hostId"] = host_id
        item["hostName"] = host.get("name")
        status = str(host.get("status") or "").lower()
        if status:
            item["isOnline"] = status in ("available", "connected")
        normalized.append(item)
    inventory["proxies"] = normalized


def collect(client: VbrClient) -> CollectionResult:
    """采集巡检所需的全部数据。"""
    result = CollectionResult()

    # ---- 先确定 REST API 版本（VBR 12 / 13 端点不同）----
    client.ensure_version()

    # ---- 先取 VBR 时钟，作为本轮的时间基准 ----
    try:
        time_payload = client.get("/api/v1/serverTime")
        if isinstance(time_payload, dict):
            vbr_now = parse_iso(time_payload.get("serverTime"))
            if vbr_now is not None:
                result.now = vbr_now
                result.clock_source = "vbr"
            else:
                result.errors.append("serverTime: 无法解析 serverTime，退回平台时钟")
        else:
            result.errors.append("serverTime: 返回格式异常，退回平台时钟")
    except AuthError:
        raise
    except VbrError as exc:
        result.errors.append(f"/api/v1/serverTime: {exc}")

    # ---- 采集其余端点 ----
    for endpoint in collect_endpoints(client.api_version):
        try:
            if endpoint.is_list:
                result.inventory[endpoint.key] = list(
                    iter_all(
                        lambda skip, limit, _p=endpoint.path: client.get(
                            _p, limit=limit, skip=skip
                        )
                    )
                )
            else:
                result.inventory[endpoint.key] = client.get(endpoint.path)
        except AuthError:
            # 认证失败不是「这个端点没数据」，必须让整轮失败
            raise
        except LicenseRestricted as exc:
            # 许可不足：主端点说明能力缺口，次端点降级为空
            result.inventory[endpoint.key] = [] if endpoint.is_list else {}
            result.errors.append(f"{endpoint.path}: 许可证限制 ({exc})")
            if endpoint.primary:
                result.degraded = True
        except NotFound as exc:
            result.inventory[endpoint.key] = [] if endpoint.is_list else {}
            result.errors.append(f"{endpoint.path}: {exc}")
            if endpoint.primary:
                result.degraded = True
        except PagingOverflow as exc:
            result.inventory[endpoint.key] = []
            result.errors.append(f"{endpoint.path}: {exc}")
            result.degraded = True
        except VbrError as exc:
            result.inventory[endpoint.key] = [] if endpoint.is_list else {}
            result.errors.append(f"{endpoint.path}: {exc}")
            if endpoint.primary:
                result.degraded = True

    _normalize_proxies(result.inventory)
    return result
