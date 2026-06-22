"""健康检查路由."""

import asyncio
import time

import redis
import sqlalchemy as sa
import urllib3
from fastapi import APIRouter, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from minio import Minio

from app.config import get_settings
from app.database import engine
from app.schemas.common import BaseResponse
from app.schemas.health import DependencyStatus, HealthReadyResponse

router = APIRouter(prefix="/health", tags=["Health"])


def _check_database() -> tuple[bool, str]:
    """检查数据库连通性."""
    try:
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))
        return True, "connected"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _check_redis() -> tuple[bool, str]:
    """检查 Redis 连通性."""
    settings = get_settings()
    try:
        client = redis.Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        if client.ping() is True:
            return True, "connected"
        return False, "ping failed"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _check_minio() -> tuple[bool, str]:
    """检查 MinIO 连通性."""
    settings = get_settings()
    try:
        http_client = urllib3.PoolManager(
            timeout=urllib3.Timeout(connect=2.0, read=3.0),
        )
        client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=False,
            http_client=http_client,
        )
        client.list_buckets()
        return True, "connected"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


@router.get("", status_code=status.HTTP_200_OK, response_model=BaseResponse)
def health_check() -> BaseResponse:
    """服务健康检查."""
    return BaseResponse(code=0, message="ok")


@router.get("/live", status_code=status.HTTP_200_OK, response_model=BaseResponse)
def liveness_check() -> BaseResponse:
    """存活探针：仅验证进程是否可响应请求."""
    return BaseResponse(code=0, message="alive")


@router.get("/ready", response_model=HealthReadyResponse)
async def readiness_check() -> JSONResponse:
    """就绪探针：检查 DB、Redis、MinIO 等关键依赖."""
    checks = {
        "database": _check_database,
        "redis": _check_redis,
        "minio": _check_minio,
    }
    results: dict[str, DependencyStatus] = {}
    all_up = True

    for name, check in checks.items():
        start = time.perf_counter() * 1000
        try:
            healthy, message = await asyncio.wait_for(
                run_in_threadpool(check),
                timeout=5.0,
            )
        except TimeoutError:
            healthy = False
            message = "check timed out"
        latency = time.perf_counter() * 1000 - start

        if not healthy:
            all_up = False
        results[name] = DependencyStatus(
            status="up" if healthy else "down",
            latency_ms=round(latency, 2),
            message=message,
        )

    content = HealthReadyResponse(
        status="ready" if all_up else "not_ready",
        dependencies=results,
    ).model_dump()
    return JSONResponse(
        status_code=status.HTTP_200_OK
        if all_up
        else status.HTTP_503_SERVICE_UNAVAILABLE,
        content=content,
    )
