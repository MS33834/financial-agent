"""Celery 应用配置.

MVP 阶段使用 Redis 作为 broker 与 result backend。
测试环境可通过 CELERY_TASK_ALWAYS_EAGER=True 同步执行任务。
"""

from celery import Celery

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
