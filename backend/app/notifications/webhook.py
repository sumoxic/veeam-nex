"""Webhook 通知：支持通用/Markdown/钉钉/飞书/企业微信模板与四种签名方式。"""
import base64
import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import quote, urlencode

import httpx

from app.notifications.base import Message, NotifyError

#: 模板列表
TEMPLATES = ("generic", "markdown", "text", "dingtalk", "feishu", "wecom")

#: 签名方式
SIGN_TYPES = ("none", "dingtalk", "feishu", "hmac_sha256")


def _feishu_text(message: Message) -> dict:
    return {
        "msg_type": "text",
        "content": {"text": f"{message.title}\n{message.body}"},
    }


def _feishu_post(message: Message) -> dict:
    return {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": message.title,
                    "content": [[{"tag": "text", "text": message.body}]],
                }
            }
        },
    }


def _feishu_interactive(message: Message) -> dict:
    return {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": message.title}},
            "elements": [{"tag": "div", "text": {"tag": "plain_text", "content": message.body}}],
        },
    }


def build_payload(template: str, message: Message) -> dict:
    """按模板生成请求体。"""
    if template == "generic":
        return message.to_dict()
    if template == "markdown":
        return {"msg_type": "markdown", "markdown": {"title": message.title, "text": message.body}}
    if template == "text":
        return {"msg_type": "text", "content": {"text": f"{message.title}\n{message.body}"}}
    if template == "dingtalk":
        return {
            "msgtype": "markdown",
            "markdown": {"title": message.title, "text": f"#### {message.title}\n\n{message.body}"},
        }
    if template == "feishu":
        if message.severity in ("critical", "warn"):
            return _feishu_interactive(message)
        return _feishu_text(message)
    if template == "wecom":
        return {
            "msgtype": "markdown",
            "markdown": {"content": f"**{message.title}**\n{message.body}"},
        }
    raise NotifyError(f"不支持的 webhook 模板: {template}")


def _sign_dingtalk(secret: str, timestamp: str) -> dict:
    """钉钉加签：HMAC-SHA256(secret, "timestamp\\nsecret") 后 base64。"""
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(
        secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256
    ).digest()
    return {"timestamp": timestamp, "sign": base64.b64encode(digest).decode("utf-8")}


def _sign_feishu(secret: str, timestamp: str) -> dict:
    """飞书加签：HMAC-SHA256(key="timestamp\\nsecret", msg=空) 后 base64。"""
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(
        string_to_sign.encode("utf-8"), b"", hashlib.sha256
    ).digest()
    return {"timestamp": timestamp, "sign": base64.b64encode(digest).decode("utf-8")}


class WebhookNotifier:
    """通过 HTTP Webhook 投递告警。"""

    def __init__(self, config: dict, secret: str | None = None,
                 headers: dict | None = None):
        self.url = config.get("url")
        self.method = (config.get("method") or "POST").upper()
        self.template = config.get("template") or "generic"
        self.sign_type = config.get("sign_type") or "none"
        self.timeout = int(config.get("timeout") or 15)
        self._secret = secret
        self._headers = dict(headers or {})

    def send(self, message: Message) -> None:
        if not self.url:
            raise NotifyError("Webhook 渠道缺少 url 配置")
        if self.template not in TEMPLATES:
            raise NotifyError(f"不支持的 webhook 模板: {self.template}")

        payload = build_payload(self.template, message)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        url = self.url
        headers = {"Content-Type": "application/json; charset=utf-8"}
        headers.update(self._headers)

        if self.sign_type != "none":
            if not self._secret:
                raise NotifyError("Webhook 渠道启用了签名但缺少密钥")
            timestamp = str(int(time.time()))
            if self.sign_type == "dingtalk":
                params = _sign_dingtalk(self._secret, timestamp)
                url = f"{url}{'&' if '?' in url else '?'}{urlencode(params)}"
            elif self.sign_type == "feishu":
                params = _sign_feishu(self._secret, timestamp)
                url = f"{url}{'&' if '?' in url else '?'}{urlencode(params)}"
            elif self.sign_type == "hmac_sha256":
                headers["X-Signature"] = hmac.new(
                    self._secret.encode("utf-8"), body, hashlib.sha256
                ).hexdigest()
            else:
                raise NotifyError(f"不支持的签名方式: {self.sign_type}")

        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                if self.method == "GET":
                    resp = client.get(url, params=payload, headers=headers)
                else:
                    resp = client.post(url, content=body, headers=headers)
        except Exception as exc:  # noqa: BLE001
            raise NotifyError(f"Webhook 请求失败: {exc}") from exc

        if resp.status_code >= 400:
            raise NotifyError(f"Webhook 返回 {resp.status_code}: {resp.text[:300]}")


def describe_templates() -> list[dict[str, Any]]:
    """给前端用的模板说明。"""
    return [
        {"value": "generic", "label": "通用 JSON"},
        {"value": "markdown", "label": "Markdown"},
        {"value": "text", "label": "纯文本"},
        {"value": "dingtalk", "label": "钉钉机器人"},
        {"value": "feishu", "label": "飞书机器人"},
        {"value": "wecom", "label": "企业微信机器人"},
    ]
