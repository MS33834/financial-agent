"""安全中间件测试."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware import RateLimitMiddleware, SecurityHeadersMiddleware


def test_security_headers_present() -> None:
    """响应应包含基础安全头."""
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/")
    def read_root() -> dict[str, str]:
        return {"ok": "true"}

    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_rate_limit_blocks_excess_requests() -> None:
    """超出限制后应返回 429."""
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        max_requests=2,
        window_seconds=60,
        key_func=lambda _request: "test-client",
    )

    @app.get("/")
    def read_root() -> dict[str, str]:
        return {"ok": "true"}

    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/").status_code == 200
        resp = client.get("/")
        assert resp.status_code == 429
        assert resp.json()["code"] == 429
        assert "Retry-After" in resp.headers
