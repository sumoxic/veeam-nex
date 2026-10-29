"""通知发送器的公共契约。"""
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class Message:
    """一条待发送的告警消息。"""

    title: str
    body: str
    severity: str = "info"
    target_name: str | None = None
    rule_key: str | None = None
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "body": self.body,
            "severity": self.severity,
            "target_name": self.target_name,
            "rule_key": self.rule_key,
            "meta": dict(self.meta),
        }


class NotifyError(Exception):
    """发送失败，调用方据此回退重试。"""


@runtime_checkable
class Notifier(Protocol):
    """渠道发送器需要实现的接口。"""

    def send(self, message: Message) -> None:
        """发送消息；失败时抛 NotifyError。"""
        ...
