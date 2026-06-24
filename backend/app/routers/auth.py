"""认证路由."""

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserInfo
from app.schemas.common import DataResponse
from app.security import create_access_token, get_current_user, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

# 登录端点简单内存限流：每 IP 每分钟最多 10 次尝试
_login_attempts: dict[str, list[float]] = {}
_LOGIN_MAX = 10
_LOGIN_WINDOW = 60.0


def _check_login_rate_limit(client_ip: str) -> None:
    """登录端点独立限流，防止暴力破解."""
    import time

    now = time.time()
    attempts = _login_attempts.get(client_ip, [])
    attempts[:] = [t for t in attempts if t > now - _LOGIN_WINDOW]
    if len(attempts) >= _LOGIN_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="登录尝试过于频繁，请稍后再试",
            headers={"Retry-After": str(int(_LOGIN_WINDOW))},
        )
    attempts.append(now)
    _login_attempts[client_ip] = attempts


@router.post("/login", response_model=DataResponse[TokenResponse])
def login(
    login_data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """用户名密码登录."""
    client_ip = request.client.host if request.client else "unknown"
    _check_login_rate_limit(client_ip)

    user = db.query(User).filter(User.username == login_data.username).first()
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.is_active != "Y":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )

    access_token = create_access_token(
        data={"sub": user.id, "tenant_id": user.tenant_id, "role": user.role},
        expires_delta=timedelta(minutes=60 * 24),
    )
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": 60 * 24 * 60,
        },
    }


@router.get("/me", response_model=DataResponse[UserInfo])
def get_me(user: User = Depends(get_current_user)) -> dict[str, Any]:
    """获取当前用户信息."""
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "tenant_id": user.tenant_id,
        },
    }
