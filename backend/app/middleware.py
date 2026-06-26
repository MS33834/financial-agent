"""生产环境加固中间件.

提供安全响应头与速率限制。
速率限制支持两种后端：
- 单实例：基于内存的固定窗口（默认）。
- 多实例：基于 Redis（``redis_url`` 传入时启用），使用 INCR + EXPIRE 计数。
"""

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from time import time

from fastapi import Request
from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.logger import get_logger

logger = get_logger(__name__)

# 安全响应头
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


def _default_rate_limit_key(request: Request) -> str:
    """默认以客户端 IP 作为限流键."""
    return request.client.host if request.client else "unknown"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """附加基础安全响应头."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """固定窗口速率限制.

    以客户端 IP 为键，默认每分钟最多 120 次请求。
    登录、Token 类接口可在路由层单独加更严格限制。

    - 未传入 ``redis_url`` 时使用进程内内存计数（仅适用于单实例）。
    - 传入 ``redis_url`` 时使用 Redis INCR + EXPIRE 计数，适用于多实例部署。
    """

    def __init__(
        self,
        app: Callable,  # type: ignore[type-arg]
        max_requests: int = 120,
        window_seconds: int = 60,
        key_func: Callable[[Request], str] = _default_rate_limit_key,
        redis_url: str | None = None,
    ) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.key_func = key_func
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
        # redis_url 为空时保持原有内存实现；传入时初始化异步 Redis 客户端
        if redis_url:
            self._redis: Redis | None = Redis.from_url(
                redis_url,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
        else:
            self._redis = None

    async def _redis_allow(self, client_ip: str) -> bool:
        """基于 Redis 的限流判定，返回当前请求是否被允许.

        首次请求时通过 EXPIRE 设置窗口；窗口内 INCR 递增计数。
        Redis 不可用时采用 fail-open 策略（放行请求并记录告警），
        避免限流依赖故障导致整体服务不可用。
        """
        key = f"ratelimit:{client_ip}"
        redis_client = self._redis
        if redis_client is None:
            return True
        try:
            count = await redis_client.incr(key)
            # 仅在计数为 1（窗口首个请求）时设置过期，避免每次请求都刷新 TTL
            if count == 1:
                await redis_client.expire(key, self.window_seconds)
        except Exception as exc:  # noqa: BLE001
            logger.warning("rate_limit_redis_error", error=str(exc))
            return True
        return count <= self.max_requests

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        client_ip = self.key_func(request)

        if self._redis is not None:
            if not await self._redis_allow(client_ip):
                return JSONResponse(
                    status_code=429,
                    content={"code": 429, "message": "Too many requests"},
                    headers={"Retry-After": str(self.window_seconds)},
                )
            return await call_next(request)

        # 内存实现：加锁保护，防止并发下的竞态条件
        now = time()
        window_start = now - self.window_seconds
        async with self._lock:
            # 清理过期记录并统计当前窗口
            records = self._requests[client_ip]
            records[:] = [t for t in records if t > window_start]

            if len(records) >= self.max_requests:
                return JSONResponse(
                    status_code=429,
                    content={"code": 429, "message": "Too many requests"},
                    headers={"Retry-After": str(self.window_seconds)},
                )

            records.append(now)

        return await call_next(request)
