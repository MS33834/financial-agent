"""审计日志相关 Schema."""

from pydantic import BaseModel, Field


class AuditLogResponse(BaseModel):
    """审计日志响应."""

    id: str = Field(description="日志 ID")
    timestamp: str = Field(description="时间戳")
    tenant_id: str | None = Field(default=None, description="租户 ID")
    user_id: str | None = Field(default=None, description="用户 ID")
    action: str = Field(description="操作")
    resource: str = Field(description="资源")
    result: str = Field(description="结果")
    ip: str | None = Field(default=None, description="IP 地址")
    reason: str | None = Field(default=None, description="原因")
