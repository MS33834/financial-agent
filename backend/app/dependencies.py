"""FastAPI 依赖项."""

from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.abac import ABACEngine
from app.database import get_db
from app.models.user import User
from app.schemas.common import PaginationParams
from app.security import decode_token, get_current_user
from app.services.api_key_service import validate_api_key


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


def require_abac_permission(
    resource_type: str,
    action: str,
) -> Callable[..., User]:
    """ABAC 权限校验依赖工厂.

    与 ``require_role`` 配合使用：先校验角色，再校验属性策略。
    """

    def _check_abac(
        user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db),
    ) -> User:
        engine = ABACEngine(db)
        if not engine.evaluate(user, resource_type, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="ABAC policy denied",
            )
        return user

    return _check_abac


def _resolve_jwt_user(authorization: str | None, db: Session) -> User | None:
    """从 Authorization: Bearer <jwt> 解析并返回活跃用户."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        payload = decode_token(authorization[7:])
    except HTTPException:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or user.is_active != "Y":
        return None
    return user


def _resolve_api_key_user(
    x_api_key: str | None,
    db: Session,
    scope: str | None,
    request: Request,
) -> User | None:
    """从 X-API-Key 解析用户并校验 scope.

    Key 存在但 scope 不足时直接抛 403，便于调用方与无效 Key 区分。
    """
    if not x_api_key:
        return None
    key_record = validate_api_key(db, x_api_key)
    if key_record is None:
        return None
    if scope is not None and not key_record.has_scope(scope):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )
    user = db.query(User).filter(User.id == key_record.user_id).first()
    if user is None or user.is_active != "Y":
        return None
    request.state.api_key_id = key_record.id
    return user


def get_current_user_or_api_key(
    scope: str | None = None,
) -> Callable[..., User]:
    """支持 JWT 或 API Key 的认证依赖工厂.

    优先尝试 ``Authorization: Bearer <jwt>``；失败时尝试 ``X-API-Key``。
    当提供 ``scope`` 时，API Key 必须拥有对应 scope，JWT 用户不受 scope 限制。
    """

    def _authenticate(
        request: Request,
        authorization: str | None = Header(default=None),
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
        db: Session = Depends(get_db),
    ) -> User:
        jwt_user = _resolve_jwt_user(authorization, db)
        if jwt_user is not None:
            return jwt_user

        api_user = _resolve_api_key_user(x_api_key, db, scope, request)
        if api_user is not None:
            return api_user

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _authenticate


def require_role_or_api_key_scope(
    *roles: str,
    scope: str | None = None,
) -> Callable[..., User]:
    """角色或 API Key scope 权限校验工厂.

    JWT 用户需满足角色要求；API Key 用户需满足 scope 要求（若提供）。
    """

    def _check(
        request: Request,
        authorization: str | None = Header(default=None),
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
        db: Session = Depends(get_db),
    ) -> User:
        jwt_user = _resolve_jwt_user(authorization, db)
        if jwt_user is not None and jwt_user.role in roles:
            return jwt_user

        if x_api_key:
            key_record = validate_api_key(db, x_api_key)
            if key_record is not None and (
                scope is None or key_record.has_scope(scope)
            ):
                user = db.query(User).filter(User.id == key_record.user_id).first()
                if user is not None and user.is_active == "Y":
                    request.state.api_key_id = key_record.id
                    return user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    return _check
