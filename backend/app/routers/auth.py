"""认证路由."""

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserInfo
from app.schemas.common import DataResponse
from app.security import create_access_token, get_current_user, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/login", response_model=DataResponse[TokenResponse])
def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """用户名密码登录."""
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
