"""容器健康检查脚本.

相比仅检查 /health，本脚本额外验证数据库、Redis 与 MinIO 连通性，
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


def _check_minio() -> bool:
    """检查 MinIO 是否可连接."""
    endpoint = os.getenv("MINIO_ENDPOINT")
    access_key = os.getenv("MINIO_ACCESS_KEY")
    secret_key = os.getenv("MINIO_SECRET_KEY")
    if not all((endpoint, access_key, secret_key)):
        return True  # 无配置时跳过

    # 上面的 all() 已保证三者均非 None，显式断言用于帮助类型检查器收窄类型。
    assert endpoint is not None and access_key is not None and secret_key is not None

    try:
        import urllib3
        from minio import Minio

        http_client = urllib3.PoolManager(
            timeout=urllib3.Timeout(connect=2.0, read=3.0),
        )
        client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=False,
            http_client=http_client,
        )
        client.list_buckets()
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"MinIO health check failed: {exc}", file=sys.stderr)
        return False


def main() -> int:
    """入口：所有检查通过返回 0，否则返回 1."""
    results = [_check_database(), _check_redis(), _check_minio()]
    if all(results):
        print("Healthy")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
