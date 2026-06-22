"""Prometheus 指标暴露.

提供 HTTP、进程级指标与业务级 Celery / 错误 / 业务计数器。
"""

from collections.abc import Awaitable, Callable
from contextlib import suppress
from time import time
from typing import Any

from fastapi import Request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    ProcessCollector,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# 统一注册表，所有自定义指标均注册于此，避免与默认 REGISTRY 混用导致重复或遗漏。
METRICS_REGISTRY = CollectorRegistry()

# 请求总数 + 耗时分布（按方法、路径、状态码分组）
HTTP_REQUESTS_TOTAL = Histogram(
    "fa_http_requests_total",
    "HTTP request total count and latency",
    ["method", "path", "status_code"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=METRICS_REGISTRY,
)

# Celery 任务指标（按 task_name 分组）
FA_TASK_RUNS_TOTAL = Counter(
    "fa_task_runs_total",
    "Total number of Celery task executions started",
    ["task_name"],
    registry=METRICS_REGISTRY,
)
FA_TASK_SUCCESS_TOTAL = Counter(
    "fa_task_success_total",
    "Total number of successful Celery task executions",
    ["task_name"],
    registry=METRICS_REGISTRY,
)
FA_TASK_FAILURES_TOTAL = Counter(
    "fa_task_failures_total",
    "Total number of failed Celery task executions",
    ["task_name"],
    registry=METRICS_REGISTRY,
)
FA_TASK_RETRIES_TOTAL = Counter(
    "fa_task_retries_total",
    "Total number of Celery task retries",
    ["task_name"],
    registry=METRICS_REGISTRY,
)
FA_TASK_DURATION_SECONDS = Histogram(
    "fa_task_duration_seconds",
    "Celery task execution duration in seconds",
    ["task_name"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
    registry=METRICS_REGISTRY,
)

# 队列深度（Redis broker）
FA_QUEUE_LENGTH = Gauge(
    "fa_queue_length",
    "Current number of messages in Celery broker queues (Redis)",
    ["queue_name"],
    registry=METRICS_REGISTRY,
)

# 错误自省：按 error_category 分类计数
FA_ERRORS_CLASSIFIED_TOTAL = Counter(
    "fa_errors_classified_total",
    "Total number of errors classified by reflection service",
    ["error_category"],
    registry=METRICS_REGISTRY,
)

# 业务操作计数器（文档 / 报告 / 审批等）
FA_BUSINESS_OPERATIONS_TOTAL = Counter(
    "fa_business_operations_total",
    "Total number of business operations",
    ["operation"],
    registry=METRICS_REGISTRY,
)

# 进程级指标
ProcessCollector(namespace="fa", registry=METRICS_REGISTRY)

_redis_client: Any | None = None


def _get_celery_app() -> Any:
    """延迟导入 Celery 应用，避免启动期循环依赖。"""
    from app.celery_app import celery_app

    return celery_app


def _get_redis_client() -> Any:
    """获取或创建 Redis 连接（用于读取队列长度）。"""
    global _redis_client
    if _redis_client is None:
        import redis

        from app.config import get_settings

        _redis_client = redis.Redis.from_url(
            get_settings().redis_url,
            decode_responses=True,
        )
    return _redis_client


def _collect_queue_names() -> set[str]:
    """从 Celery worker 获取活跃队列名；不可用时返回默认队列。"""
    with suppress(Exception):
        celery_app = _get_celery_app()
        inspect = celery_app.control.inspect(timeout=1)
        queues = inspect.active_queues() or {}
        return {
            q["name"]
            for worker_queues in queues.values()
            for q in worker_queues
            if isinstance(q, dict) and "name" in q
        }
    return {"celery"}


def update_queue_depths() -> None:
    """刷新 Redis broker 中各队列的深度到 Gauge。

    失败时静默忽略，避免影响 /metrics 端点可用性。
    """
    with suppress(Exception):
        client = _get_redis_client()
        for queue_name in _collect_queue_names():
            length = client.llen(queue_name) or 0
            FA_QUEUE_LENGTH.labels(queue_name=queue_name).set(length)


def generate_metrics() -> bytes:
    """生成 Prometheus 格式的指标数据."""
    update_queue_depths()
    return generate_latest(METRICS_REGISTRY)


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
