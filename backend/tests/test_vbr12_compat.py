"""VBR 12 兼容：端点选择与代理数据归一化。"""
from app.vbr.collector import _normalize_proxies
from app.vbr.endpoints import (
    PROXY_CONFIG_PATH,
    PROXY_STATES_PATH,
    collect_endpoints,
    inspection_endpoints,
)


def test_v12_uses_proxy_config_endpoint():
    endpoints = {item.key: item.path for item in collect_endpoints("1.2-rev1")}
    assert endpoints["proxies"] == PROXY_CONFIG_PATH
    assert PROXY_STATES_PATH in inspection_endpoints("1.3-rev2")
    assert PROXY_CONFIG_PATH in inspection_endpoints("1.2-rev1")


def test_v13_keeps_proxy_states_endpoint():
    endpoints = {item.key: item.path for item in collect_endpoints("1.3-rev2")}
    assert endpoints["proxies"] == PROXY_STATES_PATH


def test_normalize_v12_proxy_from_managed_server():
    inventory = {
        "proxies": [
            {"id": "p1", "name": "Proxy", "type": "ViProxy", "server": {"hostId": "h1"}}
        ],
        "managedServers": [{"id": "h1", "name": "esxi-01", "status": "Available"}],
    }
    _normalize_proxies(inventory)
    proxy = inventory["proxies"][0]
    assert proxy["hostName"] == "esxi-01"
    assert proxy["hostId"] == "h1"
    assert proxy["isOnline"] is True


def test_normalize_keeps_v13_states_untouched():
    proxy = {"id": "p1", "name": "Proxy", "isOnline": False, "hostName": "esxi-01"}
    inventory = {"proxies": [proxy]}
    _normalize_proxies(inventory)
    assert inventory["proxies"][0] is proxy
