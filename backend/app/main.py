"""FastAPI 应用入口."""

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.responses import Response

from app.config import get_settings
from app.database import Base, engine
from app.logger import configure_logging, get_logger
from app.metrics import PrometheusMiddleware, metrics_response
from app.middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from app.routers import (
    access_policies,
    admin,
    agent,
    api_keys,
    approvals,
    audit,
    auth,
    dashboard,
    dify_tools,
    documents,
    health,
    im,
    im_user_mappings,
    notifications,
    queries,
    reflections,
    reports,
    users,
)

logger = get_logger(__name__)


def _validate_production_config() -> None:
    """生产环境启动前强校验敏感配置，拒绝弱密钥/不安全默认值启动.

    只在 app_env == "production" 时执行，开发/测试环境跳过。
    """
    settings = get_settings()
    if settings.app_env != "production":
        return

    # 已知弱 SECRET_KEY 默认值（来自 .env.example / backend/.env.example）
    weak_secret_keys = {
        "change-me-in-production-32-char-min",
        "change-me-to-a-random-secret-key",
        "your-secret-key",
        "secret-key",
    }
    if not settings.secret_key or settings.secret_key in weak_secret_keys:
        raise RuntimeError(
            "生产环境启动被拒绝：SECRET_KEY 为空或使用了示例默认值。"
            "请通过环境变量设置一个不少于 32 字符的随机密钥。"
        )
    if len(settings.secret_key) < 32:
        raise RuntimeError(
            f"生产环境启动被拒绝：SECRET_KEY 长度仅 {len(settings.secret_key)} 字符，"
            "要求至少 32 字符。请使用 `openssl rand -hex 32` 生成。"
        )

    # CORS 通配符在生产环境会放大 CSRF / 凭证泄露风险，直接拒绝
    if settings.cors_origins_list == ["*"]:
        raise RuntimeError(
            "生产环境启动被拒绝：CORS_ORIGINS 为通配符 '*'。"
            "请显式配置允许的前端域名（逗号分隔），例如 https://fa.example.com。"
        )

    logger.info("production_config_validated")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期管理."""
    configure_logging()
    settings = get_settings()
    # 生产环境强校验：弱密钥 / CORS 通配符等不安全配置直接 fail-fast
    _validate_production_config()
    logger.info(
        "starting_up",
        app_name=settings.app_name,
        env=settings.app_env,
    )
    # 开发/测试环境自动建表；生产环境应使用 Alembic 迁移
    if settings.app_env in ("development", "testing"):
        await run_in_threadpool(Base.metadata.create_all, bind=engine)
        logger.info("database_tables_created")
    yield
    logger.info("shutting_down")
    # 优雅关闭：释放数据库连接池，避免正在处理的请求被强制中断
    await run_in_threadpool(engine.dispose)
    logger.info("engine_disposed")


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例."""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.2.0",
        description="企业级财务智能体后端 API",
        lifespan=lifespan,
    )

    # CORS（生产环境通过 CORS_ORIGINS 限制为前端域名）
    # 安全规则：通配符 "*" 不能与 allow_credentials=True 同时使用，
    # 否则任意源都能携带凭证访问，存在 CSRF/凭证泄露风险。
    cors_origins = settings.cors_origins_list
    is_wildcard = cors_origins == ["*"]
    if is_wildcard:
        logger.warning(
            "cors_wildcard_with_credentials_disabled",
            detail="CORS_ORIGINS 为通配符 '*'，已自动禁用 allow_credentials；"
            "生产环境请显式配置 CORS_ORIGINS 为前端域名以启用凭证传递",
        )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=not is_wildcard,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Request-ID"],
    )

    # 基础安全头
    app.add_middleware(SecurityHeadersMiddleware)

    # 请求速率限制（单实例内存实现，多实例需使用 Redis/网关）
    if settings.rate_limit_enabled:
        app.add_middleware(
            RateLimitMiddleware,
            max_requests=settings.rate_limit_max_requests,
            window_seconds=settings.rate_limit_window_seconds,
        )

    # Prometheus HTTP 指标采集
    app.add_middleware(PrometheusMiddleware)

    # 注入 request_id 并记录请求日志
    @app.middleware("http")
    async def add_request_id(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # 全局异常处理
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.error(
            "unhandled_exception",
            request_id=request_id,
            path=request.url.path,
            error=str(exc),
        )
        return JSONResponse(
            status_code=500,
            content={
                "code": 500,
                "message": "Internal server error",
                "request_id": request_id,
            },
        )

    # 注册路由
    app.include_router(health.router)
    app.include_router(admin.router)
    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.include_router(documents.router)
    app.include_router(queries.router)
    app.include_router(reports.router)
    app.include_router(approvals.router)
    app.include_router(audit.router)
    app.include_router(access_policies.router)
    app.include_router(dify_tools.router)
    app.include_router(im.router)
    app.include_router(im_user_mappings.router)
    app.include_router(notifications.router)
    app.include_router(api_keys.router)
    app.include_router(agent.router)
    app.include_router(reflections.router)
    app.include_router(users.router)

    # Prometheus 指标端点（标准 /metrics，不进入 API 文档）
    @app.get("/metrics", include_in_schema=False)
    def _metrics() -> Response:
        return metrics_response()

    return app


app = create_app()
