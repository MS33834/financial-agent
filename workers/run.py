"""Celery Worker 启动入口（独立模块版）.

提供比 scripts/worker.py 更完善的启动流程：
- 启动前配置日志
- 健康检查信号注册
- 优雅关闭
- 单进程/多进程切换
"""

from __future__ import annotations

import os
import signal
import sys

# 将 backend 目录加入路径，使 app 包可被导入
_BACKEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.celery_app import celery_app  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.logger import configure_logging, get_logger  # noqa: E402

logger = get_logger(__name__)

_graceful_shutdown = False


def _handle_sigterm(signum: int, _frame: object) -> None:
    """优雅关闭：收到 SIGTERM/SIGINT 后标记关闭，等待当前任务完成."""
    global _graceful_shutdown  # noqa: PLW0603
    if _graceful_shutdown:
        logger.warning("worker_force_shutdown", signal=signum)
        sys.exit(1)
    _graceful_shutdown = True
    logger.info("worker_graceful_shutdown_started", signal=signum)
    # celery 的 worker 会自行处理优雅关闭
    celery_app.control.shutdown()


def main() -> None:
    """启动 Celery Worker."""
    configure_logging()
    settings = get_settings()

    if settings.task_backend.lower() != "celery":
        logger.error(
            "worker_start_rejected",
            reason=f"TASK_BACKEND={settings.task_backend}, expected 'celery'",
        )
        print(
            f"TASK_BACKEND={settings.task_backend}，当前为同步模式，无需启动 Celery Worker。\n"
            "如需异步任务，请设置 TASK_BACKEND=celery 并配置 REDIS_URL。",
            file=sys.stderr,
        )
        sys.exit(1)

    # 注册信号处理
    signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGINT, _handle_sigterm)

    concurrency = int(os.environ.get("CELERY_WORKER_CONCURRENCY", "2"))
    logger.info(
        "worker_starting",
        concurrency=concurrency,
        log_level=settings.log_level,
    )

    argv = [
        "worker",
        f"--loglevel={settings.log_level.lower()}",
        f"--concurrency={concurrency}",
    ]

    # 健康检查队列：celery inspect ping 可用于 healthcheck
    celery_app.conf.update(
        worker_hijack_root_logger=False,
        worker_max_tasks_per_child=1000,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
    )

    celery_app.start(argv)


if __name__ == "__main__":
    main()
