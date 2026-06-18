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

if __name__ == "__main__":
    argv = [
        "worker",
        "--loglevel=info",
        "--concurrency=2",
    ]
    celery_app.start(argv)
