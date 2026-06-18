"""FastAPI 依赖项."""

from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.schemas.common import PaginationParams
from app.security import get_current_user


def require_dify_api_key(x_api_key: str | None = Header(default=None)) -> str:
    """校验 Dify 调用后端 Tools 时携带的 API Key.

    Dify HTTP Request 节点需在 Header 中设置 ``X-API-Key``。
    """
    settings = get_settings()
    expected = settings.dify_tool_api_key
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="DIFY_TOOL_API_KEY not configured",
        )
    if not x_api_key or x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Dify API Key",
        )
    return x_api_key


def get_pagination(params: PaginationParams = Depends()) -> PaginationParams:
    """分页参数依赖."""
    return params


def require_role(*roles: str) -> Callable[[User], User]:
    """角色权限校验依赖工厂."""

    def _check_role(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied",
            )
        return user

    return _check_role


def get_current_active_user(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """获取当前活跃用户."""
    if user.is_active != "Y":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return user
