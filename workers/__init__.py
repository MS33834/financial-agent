"""独立 Worker 模块.

当 TASK_BACKEND=celery 时，通过此模块启动独立 Worker 进程，
支持健康检查、优雅关闭与任务监控。

启动方式：
    python -m workers.run

等价于：
    celery -A app.celery_app worker --loglevel=info --concurrency=2
"""

from workers.run import main

__all__ = ["main"]
