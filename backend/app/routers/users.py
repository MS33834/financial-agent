"""用户管理路由.

提供管理员维护租户内用户的 CRUD 与密码重置接口。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.roles import Role
from app.database import get_db
from app.dependencies import get_pagination, require_role
from app.models.user import User
from app.schemas.common import DataResponse, PaginatedResponse, PaginationParams
from app.schemas.user import (
    ResetPasswordRequest,
    UserCreate,
    UserResponse,
    UserUpdate,
    serialize_user,
)
from app.security import get_password_hash

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


@router.get("", response_model=PaginatedResponse[dict[str, Any]])
def list_users(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
    pagination: PaginationParams = Depends(get_pagination),
) -> dict[str, Any]:
    """查询当前租户下的用户列表."""
    query = db.query(User).filter(User.tenant_id == user.tenant_id)
    total = query.count()
    items = (
        query.order_by(User.created_at.desc())
        .offset((pagination.page - 1) * pagination.page_size)
        .limit(pagination.page_size)
        .all()
    )
    return {
        "data": {
            "items": [serialize_user(item) for item in items],
            "total": total,
            "page": pagination.page,
            "page_size": pagination.page_size,
        }
    }


@router.post(
    "",
    response_model=DataResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> dict[str, Any]:
    """创建用户."""
    new_user = User(
        tenant_id=user.tenant_id,
        username=payload.username,
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        role=payload.role,
        is_active=payload.is_active,
    )
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        # 唯一约束冲突：同租户下用户名已存在
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在",
        ) from None
    db.refresh(new_user)
    return {
        "code": 0,
        "message": "ok",
        "data": serialize_user(new_user),
    }


@router.put("/{user_id}", response_model=DataResponse[UserResponse])
def update_user(
    user_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> dict[str, Any]:
    """更新用户信息（邮箱 / 角色 / 启用状态 / 密码）."""
    target: User | None = (
        db.query(User)
        .filter(User.id == user_id, User.tenant_id == user.tenant_id)
        .first()
    )
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    if payload.email is not None:
        target.email = payload.email
    if payload.role is not None:
        target.role = payload.role
    if payload.is_active is not None:
        target.is_active = payload.is_active
    if payload.password:
        target.hashed_password = get_password_hash(payload.password)

    db.commit()
    db.refresh(target)
    return {
        "code": 0,
        "message": "ok",
        "data": serialize_user(target),
    }


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> None:
    """删除用户."""
    target: User | None = (
        db.query(User)
        .filter(User.id == user_id, User.tenant_id == user.tenant_id)
        .first()
    )
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )
    # 防止管理员误删自己导致无法登录
    if target.id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除当前登录用户",
        )
    db.delete(target)
    db.commit()


@router.post("/{user_id}/reset-password", response_model=DataResponse[dict[str, Any]])
def reset_password(
    user_id: str,
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> dict[str, Any]:
    """重置指定用户的密码."""
    target: User | None = (
        db.query(User)
        .filter(User.id == user_id, User.tenant_id == user.tenant_id)
        .first()
    )
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )
    target.hashed_password = get_password_hash(payload.password)
    db.commit()
    return {
        "code": 0,
        "message": "ok",
        "data": {"id": target.id, "reset": True},
    }
