"""结构化日志配置。

- 同时输出到 stdout 与 backend/logs/ 下的按天滚动文件
- 每行一条 JSON，便于后续采集与检索
- 通过 contextvar 传递 request_id / target_id / run_id 等链路标识

实现说明：loguru 的 `format` 回调返回的是**格式模板**而不是最终文本，
直接返回 JSON 会被当成模板再次解析。因此这里用 patcher 在记录生成后把整条
JSON 写进 `record["message"]`，再用最简的 `{message}` 模板输出。
"""
import json
import logging
import sys
import traceback
from contextvars import ContextVar
from pathlib import Path

from loguru import logger as _loguru_logger

from app.config import get_settings

# 请求链路上下文：middleware 与业务代码通过 bind_context() 注入
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
context_vars: ContextVar[dict] = ContextVar("log_context", default={})


class InterceptHandler(logging.Handler):
    """把标准库 logging 记录转发给 loguru。"""

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D102
        try:
            level = _loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        _loguru_logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def _flatten_extra(record: dict) -> dict:
    """取出结构化字段。

    loguru 把 `logger.info(msg, extra={...})` 的 extra 当成格式化关键字参数，
    最终落在 record["extra"]["extra"] 里；这里统一摊平。
    """
    extra = dict(record.get("extra") or {})
    if set(extra.keys()) == {"extra"} and isinstance(extra["extra"], dict):
        extra = dict(extra["extra"])
    return extra


def _patch_record(record: dict) -> None:
    """patcher：把一条日志记录改写成完整的单行 JSON。"""
    exception = record.get("exception")
    payload = {
        "ts": record["time"].isoformat(),
        "level": record["level"].name,
        "logger": record["name"],
        "message": record["message"],
        "request_id": request_id_var.get(),
    }
    payload.update(context_vars.get() or {})
    for key, value in _flatten_extra(record).items():
        payload.setdefault(key, value)
    if exception:
        payload["exception"] = "".join(
            traceback.format_exception(*exception)
        ).strip()

    record["message"] = json.dumps(payload, ensure_ascii=False, default=str)
    record["extra"] = {}
    # 异常已经进 JSON，不再让模板追加一次栈信息
    record["exception"] = None


#: 需要包装 extra= 的日志级别方法
_LOG_METHODS = (
    "log", "debug", "info", "success", "warning", "error", "critical", "exception", "trace",
)


class _Logger:
    """loguru 的薄封装，支持 `logger.info("msg", extra={...})` 写法。

    loguru 原生没有 extra 关键字参数，直接传会被当成消息格式化参数，
    遇到消息里带花括号就会抛 KeyError。
    """

    def __init__(self, inner):
        self._inner = inner

    def bind(self, **kwargs) -> "_Logger":
        """绑定上下文字段。"""
        return _Logger(self._inner.bind(**kwargs))

    def opt(self, **kwargs) -> "_Logger":
        """透传 loguru 的 opt（exception=True 等）。"""
        return _Logger(self._inner.opt(**kwargs))

    def __getattr__(self, name):
        attr = getattr(self._inner, name)
        if name not in _LOG_METHODS or not callable(attr):
            return attr

        def wrapper(message, *args, extra=None, **kwargs):
            target = self._inner.bind(**extra) if extra else self._inner
            return getattr(target, name)(message, *args, **kwargs)

        return wrapper


#: 对外暴露的 logger
logger = _Logger(_loguru_logger)


def setup_logging() -> None:
    """初始化日志系统，应在应用启动时调用一次。"""
    settings = get_settings()
    log_dir = settings.log_path
    log_dir.mkdir(parents=True, exist_ok=True)

    _loguru_logger.remove()
    _loguru_logger.configure(patcher=_patch_record)
    _loguru_logger.add(
        sys.stdout,
        level=settings.log_level,
        format="{message}",
        enqueue=False,
        backtrace=False,
        diagnose=False,
    )
    _loguru_logger.add(
        Path(log_dir) / "platform_{time:YYYY-MM-DD}.log",
        level=settings.log_level,
        rotation="1 day",
        retention=f"{settings.log_retention_days} days",
        encoding="utf-8",
        format="{message}",
        enqueue=True,
        backtrace=False,
        diagnose=False,
    )

    # 接管标准库日志
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine"):
        std_logger = logging.getLogger(name)
        std_logger.handlers = [InterceptHandler()]
        std_logger.propagate = False

    logger.info(
        "logging initialised",
        extra={"log_dir": str(log_dir), "level": settings.log_level},
    )


def bind_context(**kwargs) -> None:
    """把链路上下文写入当前 contextvar，供后续日志自动携带。"""
    current = dict(context_vars.get() or {})
    current.update({k: v for k, v in kwargs.items() if v is not None})
    context_vars.set(current)


def clear_context() -> None:
    """清理链路上下文。"""
    context_vars.set({})


__all__ = [
    "logger",
    "setup_logging",
    "bind_context",
    "clear_context",
    "request_id_var",
    "context_vars",
]
