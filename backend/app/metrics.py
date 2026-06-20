"""Prometheus 指标暴露.

提供基础进程指标与 HTTP 请求耗时/总量 histogram。
"""

from collections.abc import Awaitable, Callable
from time import time

from fastapi import Request
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# 请求总数 + 耗时分布（按方法、路径、状态码分组）
HTTP_REQUESTS_TOTAL = Histogram(
    "fa_http_requests_total",
    "HTTP request total count and latency",
    ["method", "path", "status_code"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)


def generate_metrics() -> bytes:
    """生成 Prometheus 格式的指标数据."""
    registry = CollectorRegistry()
    # 自动收集进程级指标
    from prometheus_client import ProcessCollector

    ProcessCollector(namespace="fa", registry=registry)
    return generate_latest(registry)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """记录 HTTP 请求耗时与总量."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time()
        response = await call_next(request)
        duration = time() - start
        status_code = str(response.status_code)
        HTTP_REQUESTS_TOTAL.labels(
            method=request.method,
            path=request.url.path,
            status_code=status_code,
        ).observe(duration)
        return response


def metrics_response() -> Response:
    """返回 /metrics 响应."""
    return Response(
        content=generate_metrics(),
        media_type=CONTENT_TYPE_LATEST,
    )
