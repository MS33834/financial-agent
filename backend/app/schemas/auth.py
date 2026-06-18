"""认证相关 Schema."""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """登录请求."""

    username: str = Field(description="用户名")
    password: str = Field(description="密码")


class TokenResponse(BaseModel):
    """登录响应."""

    access_token: str = Field(description="访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(description="有效期（秒）")


class UserInfo(BaseModel):
    """当前用户信息."""

    id: str = Field(description="用户 ID")
    username: str = Field(description="用户名")
    role: str = Field(description="角色")
    tenant_id: str = Field(description="租户 ID")
