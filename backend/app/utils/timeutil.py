"""时间处理工具。

平台内部一律使用 UTC；只有在与 VBR 时钟比较时才使用 VBR 返回的时间戳。
"""
from datetime import datetime, timezone
from typing import Optional


def utcnow() -> datetime:
    """当前 UTC 时间（带时区）。"""
    return datetime.now(timezone.utc)


def to_utc_naive(dt: datetime) -> datetime:
    """转成 naive UTC，用于写入 MySQL DATETIME 列。"""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def parse_iso(value: Optional[str]) -> Optional[datetime]:
    """解析 ISO8601 时间串；无时区信息时按 UTC 处理。"""
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def age_hours(reference: datetime, moment: Optional[datetime]) -> Optional[float]:
    """计算两个时刻之间相差多少小时（可为负）。"""
    if moment is None or reference is None:
        return None
    return (reference - moment).total_seconds() / 3600.0
