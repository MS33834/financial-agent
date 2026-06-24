"""ABAC 策略 Schema."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class AccessPolicyCreate(BaseModel):
    """创建访问策略."""

    name: str = Field(description="策略名称", min_length=1)
    resource_type: str = Field(description="资源类型，如 report")
    action: str = Field(description="操作，如 read")
    effect: Literal["allow", "deny"] = Field(default="allow", description="allow 或 deny")
    priority: int = Field(default=100, description="优先级，越小越优先")
    conditions: dict[str, Any] | None = Field(default=None, description="策略条件")
    description: str | None = Field(default=None, description="策略描述")
    is_active: bool = Field(default=True, description="是否启用")


class AccessPolicyUpdate(BaseModel):
    """更新访问策略."""

    name: str | None = Field(default=None, description="策略名称")
    resource_type: str | None = Field(default=None, description="资源类型")
    action: str | None = Field(default=None, description="操作")
    effect: Literal["allow", "deny"] | None = Field(default=None, description="allow 或 deny")
    priority: int | None = Field(default=None, description="优先级")
    conditions: dict[str, Any] | None = Field(default=None, description="策略条件")
    description: str | None = Field(default=None, description="策略描述")
    is_active: bool | None = Field(default=None, description="是否启用")


class AccessPolicyResponse(BaseModel):
    """访问策略响应."""

    id: str
    tenant_id: str
    name: str
    resource_type: str
    action: str
    effect: str
    priority: int
    conditions: dict[str, Any] | None
    description: str | None
    is_active: bool
