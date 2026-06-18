"""FastAPI 依赖项."""

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.common import PaginationParams
from app.security import get_current_user


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
