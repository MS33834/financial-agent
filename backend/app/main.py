"""FastAPI 应用入口."""

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.responses import Response

from app.config import get_settings
from app.database import Base, engine
from app.logger import configure_logging, get_logger
from app.routers import (
    access_policies,
    api_keys,
    approvals,
    audit,
    auth,
    dify_tools,
    documents,
    health,
    im,
    im_user_mappings,
    queries,
    reports,
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期管理."""
    configure_logging()
    settings = get_settings()
    logger.info(
        "starting_up",
        app_name=settings.app_name,
        env=settings.app_env,
    )
    # 开发/测试环境自动建表；生产环境应使用 Alembic 迁移
    if settings.app_env in ("development", "testing"):
        Base.metadata.create_all(bind=engine)
        logger.info("database_tables_created")
    yield
    logger.info("shutting_down")


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例."""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="企业级财务智能体后端 API",
        lifespan=lifespan,
    )

    # CORS（MVP 放开本地开发，生产按域名限制）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
    app.include_router(auth.router)
    app.include_router(documents.router)
    app.include_router(queries.router)
    app.include_router(reports.router)
    app.include_router(approvals.router)
    app.include_router(audit.router)
    app.include_router(access_policies.router)
    app.include_router(dify_tools.router)
    app.include_router(im.router)
    app.include_router(im_user_mappings.router)
    app.include_router(api_keys.router)

    return app


app = create_app()
