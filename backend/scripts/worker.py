"""Celery Worker 启动脚本.

用法：
    python scripts/worker.py

等价于：
    celery -A app.celery_app worker --loglevel=info
"""

import os
import sys

# 将 backend 目录加入路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.celery_app import celery_app
from app.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    if settings.task_backend.lower() != "celery":
        print(
            f"TASK_BACKEND={settings.task_backend}，当前为同步模式，无需启动 Celery Worker。"
            "如需异步任务，请设置 TASK_BACKEND=celery 并配置 REDIS_URL。",
            file=sys.stderr,
        )
        sys.exit(1)

    argv = [
        "worker",
        "--loglevel=info",
        "--concurrency=2",
    ]
    celery_app.start(argv)
