"""管理后台路由."""

from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.config import reload_settings
from app.core.roles import Role
from app.dependencies import require_abac_permission, require_role
from app.models.user import User
from app.storage import get_storage_client

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


class ConfigReloadResponse(BaseModel):
    """配置重载响应."""

    code: int = Field(default=0, description="业务状态码")
    message: str = Field(..., description="提示信息")
    data: dict[str, Any] = Field(
        default_factory=dict, description="当前生效的非敏感配置项"
    )


@router.post(
    "/reload-config",
    response_model=ConfigReloadResponse,
    status_code=status.HTTP_200_OK,
)
def reload_config(
    user: User = Depends(require_role(Role.ADMIN)),
    _abac: User = Depends(require_abac_permission("system_config", "reload")),
) -> ConfigReloadResponse:
    """运行时重新加载环境变量 / .env 配置文件.

    需要管理员角色，并满足 ``system_config:reload`` ABAC 策略。
    重新加载后会清空存储客户端缓存，使新的 MinIO 等配置在后续调用中生效。
    """
    settings = reload_settings()
    get_storage_client.cache_clear()

    safe_config = {
        "app_name": settings.app_name,
        "app_env": settings.app_env,
        "debug": settings.debug,
        "log_level": settings.log_level,
        "rate_limit_enabled": settings.rate_limit_enabled,
        "rate_limit_max_requests": settings.rate_limit_max_requests,
        "rate_limit_window_seconds": settings.rate_limit_window_seconds,
    }
    return ConfigReloadResponse(
        code=0,
        message="Configuration reloaded",
        data=safe_config,
    )
