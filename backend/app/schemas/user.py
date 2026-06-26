"""用户管理相关 Schema."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# 用户角色白名单（与 app.core.roles.Role 保持一致）
UserRole = Literal["admin", "finance_manager", "auditor", "viewer"]


class UserCreate(BaseModel):
    """创建用户请求."""

    username: str = Field(..., min_length=1, max_length=64, description="用户名")
    email: str | None = Field(default=None, max_length=128, description="邮箱")
    password: str = Field(..., min_length=6, max_length=128, description="密码")
    role: UserRole = Field(default="viewer", description="角色")
    is_active: str = Field(default="Y", description="是否启用: Y/N")


class UserUpdate(BaseModel):
    """更新用户请求."""

    email: str | None = Field(default=None, max_length=128, description="邮箱")
    role: UserRole | None = Field(default=None, description="角色")
    is_active: str | None = Field(default=None, description="是否启用: Y/N")
    password: str | None = Field(
        default=None, min_length=6, max_length=128, description="新密码，留空不修改"
    )


class ResetPasswordRequest(BaseModel):
    """重置密码请求."""

    password: str = Field(..., min_length=6, max_length=128, description="新密码")


class UserResponse(BaseModel):
    """用户响应（不含密码哈希）."""

    id: str
    username: str
    email: str | None = None
    role: str
    is_active: str
    created_at: str | None = None


def serialize_user(user: Any) -> dict[str, Any]:
    """将 User ORM 对象序列化为响应字典（不含密码哈希）."""
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
