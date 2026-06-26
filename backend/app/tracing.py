"""OpenTelemetry 链路追踪集成（可选依赖）.

为避免强制引入 otel 依赖，导入失败时所有功能降级为空操作。
启用方式：安装 ``opentelemetry-distro`` 及相关 exporter/instrumentation 包，
并在调用 :func:`setup_tracing` 时传入 ``otlp_endpoint``。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# 探测 opentelemetry 是否可用，未安装时降级
_OTEL_AVAILABLE = False
try:  # pragma: no cover - 依赖安装与否决定分支
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover - 未安装 otel 时走此分支
    _OTEL_AVAILABLE = False

# 防止重复初始化 TracerProvider（OTel 仅允许设置一次）
_TRACING_INITIALIZED = False


def setup_tracing(app_name: str, otlp_endpoint: str | None = None) -> None:
    """初始化 OpenTelemetry 链路追踪.

    - 未安装 opentelemetry 或未提供 ``otlp_endpoint`` 时，记录日志并跳过；
    - 否则配置 TracerProvider + OTLP HTTP exporter，并准备 FastAPI instrumentation。

    Args:
        app_name: 服务名，作为 OTel resource 的 ``service.name``。
        otlp_endpoint: OTLP HTTP 端点，如 ``http://otel-collector:4318/v1/traces``。
    """
    global _TRACING_INITIALIZED  # noqa: PLW0603 - 模块级单例初始化状态
    if not _OTEL_AVAILABLE:
        logger.info("opentelemetry 未安装，跳过链路追踪初始化")
        return
    if not otlp_endpoint:
        logger.info("未配置 OTLP endpoint，跳过链路追踪初始化")
        return
    if _TRACING_INITIALIZED:
        logger.info("链路追踪已初始化，跳过重复配置")
        return

    # 配置 TracerProvider 与 OTLP exporter
    resource = Resource.create({"service.name": app_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    _TRACING_INITIALIZED = True
    logger.info("otel_tracing_configured app_name=%s otlp_endpoint=%s", app_name, otlp_endpoint)


def instrument_fastapi(app: Any) -> None:
    """对 FastAPI 应用启用自动 instrumentation.

    未安装 opentelemetry 时为空操作，便于在 ``main.py`` 中无条件调用。
    """
    if not _OTEL_AVAILABLE:
        return
    FastAPIInstrumentor.instrument_app(app)
    logger.info("otel_fastapi_instrumented")
