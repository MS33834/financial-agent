"""API Key 相关 Schema."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    """创建 API Key 请求."""

    name: str = Field(..., min_length=1, max_length=128, description="Key 名称")
    scopes: list[str] = Field(
        default_factory=list,
        description="权限范围，如 ['queries:nl2sql', 'reports:read']；空表示全部",
    )
    expires_at: datetime | None = Field(default=None, description="过期时间")


class ApiKeyResponse(BaseModel):
    """API Key 列表/详情响应."""

    id: str
    tenant_id: str
    user_id: str
    name: str
    scopes: list[str]
    is_active: str
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ApiKeyCreateResponse(ApiKeyResponse):
    """创建 API Key 响应，额外返回一次明文 key."""

    key: str = Field(..., description="API Key 明文，仅创建时返回一次")


class ApiKeyListResponse(BaseModel):
    """API Key 列表分页响应."""

    items: list[ApiKeyResponse]
    total: int
    page: int
    page_size: int
