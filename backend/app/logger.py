"""结构化日志配置."""

import logging
import sys
from collections.abc import Mapping, MutableMapping
from typing import Any

import structlog

from app.config import get_settings


def inject_trace_context(
    _logger: Any,
    _method_name: str,
    event_dict: MutableMapping[str, Any],
) -> Mapping[str, Any]:
    """structlog processor：将当前 OTel trace_id / span_id 注入日志事件.

    OpenTelemetry 的当前 span 通过 contextvars 传播，此处读取
    ``trace.get_current_span()`` 即等同于从 contextvars 获取上下文。
    未安装 opentelemetry 或无活跃 span 时保持原事件不变。
    """
    try:  # pragma: no cover - 依赖安装与否决定分支
        from opentelemetry import trace
    except ImportError:
        return event_dict

    span = trace.get_current_span()
    if span is None:
        return event_dict
    ctx = span.get_span_context()
    if ctx is not None and ctx.is_valid:
        # trace_id / span_id 为整型，统一格式化为十六进制字符串
        event_dict["trace_id"] = f"{ctx.trace_id:032x}"
        event_dict["span_id"] = f"{ctx.span_id:016x}"
    return event_dict


def configure_logging() -> None:
    """配置结构化日志."""
    settings = get_settings()

    # 标准库日志级别
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    # 配置 structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            # 注入当前链路追踪上下文，便于日志与 trace 关联
            inject_trace_context,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """获取日志记录器."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]
