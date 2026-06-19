"""生产环境加固中间件.

提供安全响应头与基于内存的速率限制。
多实例部署时应替换为 Redis / 网关层限流。
"""

from collections import defaultdict
from collections.abc import Awaitable, Callable
from time import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

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
    """基于内存的固定窗口速率限制.

    以客户端 IP 为键，默认每分钟最多 120 次请求。
    登录、Token 类接口可在路由层单独加更严格限制。
    """

    def __init__(
        self,
        app: Callable,  # type: ignore[type-arg]
        max_requests: int = 120,
        window_seconds: int = 60,
        key_func: Callable[[Request], str] = _default_rate_limit_key,
    ) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.key_func = key_func
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        client_ip = self.key_func(request)
        now = time()
        window_start = now - self.window_seconds

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
