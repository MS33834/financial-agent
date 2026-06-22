"""Celery 应用配置.

MVP 阶段使用 Redis 作为 broker 与 result backend。
测试环境可通过 CELERY_TASK_ALWAYS_EAGER=True 同步执行任务。
"""

from contextlib import suppress
from time import monotonic
from typing import Any

from celery import Celery
from celery.signals import task_failure, task_postrun, task_prerun, task_retry

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "financial_agent",
    broker=settings.celery_broker_url or settings.redis_url,
    backend=settings.celery_result_backend or settings.redis_url,
    include=["app.tasks.document_tasks", "app.tasks.report_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,
    task_soft_time_limit=300,
    # 测试环境可在 .env 中设置为 True，使任务同步执行
    task_always_eager=settings.app_env == "testing",
)

# 记录任务开始时间：task_id -> monotonic
_task_start_times: dict[str | None, float] = {}


@task_prerun.connect  # type: ignore[untyped-decorator]
def _metrics_task_prerun(
    sender: Any = None,
    task_id: str | None = None,
    task: Any = None,
    **kwargs: Any,
) -> None:
    """任务开始执行时记录启动时间与运行计数。"""
    with suppress(Exception):
        if task is not None:
            from app.metrics import FA_TASK_RUNS_TOTAL

            FA_TASK_RUNS_TOTAL.labels(task_name=task.name).inc()
        if task_id is not None:
            _task_start_times[task_id] = monotonic()


@task_postrun.connect  # type: ignore[untyped-decorator]
def _metrics_task_postrun(
    sender: Any = None,
    task_id: str | None = None,
    task: Any = None,
    state: str | None = None,
    **kwargs: Any,
) -> None:
    """任务执行结束后记录耗时；成功状态额外计数。"""
    with suppress(Exception):
        if task is not None and task_id is not None:
            start = _task_start_times.pop(task_id, None)
            if start is not None:
                duration = monotonic() - start
                from app.metrics import FA_TASK_DURATION_SECONDS

                FA_TASK_DURATION_SECONDS.labels(task_name=task.name).observe(duration)
        if state == "SUCCESS" and task is not None:
            from app.metrics import FA_TASK_SUCCESS_TOTAL

            FA_TASK_SUCCESS_TOTAL.labels(task_name=task.name).inc()


@task_failure.connect  # type: ignore[untyped-decorator]
def _metrics_task_failure(sender: Any = None, **kwargs: Any) -> None:
    """任务最终失败时计数（重试不会触发此信号）。"""
    with suppress(Exception):
        if sender is not None:
            from app.metrics import FA_TASK_FAILURES_TOTAL

            FA_TASK_FAILURES_TOTAL.labels(task_name=sender.name).inc()


@task_retry.connect  # type: ignore[untyped-decorator]
def _metrics_task_retry(sender: Any = None, **kwargs: Any) -> None:
    """任务发起重试时计数。"""
    with suppress(Exception):
        if sender is not None:
            from app.metrics import FA_TASK_RETRIES_TOTAL

            FA_TASK_RETRIES_TOTAL.labels(task_name=sender.name).inc()
