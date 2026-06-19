"""容器健康检查脚本.

相比仅检查 /health，本脚本额外验证数据库与 Redis 连通性，
便于 orchestrator 在依赖就绪后再标记服务健康。
"""

from __future__ import annotations

import os
import sys


def _check_database() -> bool:
    """检查 PostgreSQL/SQLite 是否可连接."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return True  # 无配置时跳过

    try:
        import sqlalchemy as sa

        engine = sa.create_engine(database_url)
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"Database health check failed: {exc}", file=sys.stderr)
        return False


def _check_redis() -> bool:
    """检查 Redis 是否可连接."""
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        return True  # 无配置时跳过

    try:
        import redis

        client = redis.Redis.from_url(redis_url, socket_connect_timeout=2)
        return client.ping() is True
    except Exception as exc:  # noqa: BLE001
        print(f"Redis health check failed: {exc}", file=sys.stderr)
        return False


def main() -> int:
    """入口：所有检查通过返回 0，否则返回 1."""
    results = [_check_database(), _check_redis()]
    if all(results):
        print("Healthy")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
