"""健康检查相关 Schema."""

from pydantic import BaseModel, Field


class DependencyStatus(BaseModel):
    """单个依赖状态."""

    status: str = Field(..., description="状态: up / down")
    latency_ms: float = Field(..., description="检查耗时（毫秒）")
    message: str | None = Field(default=None, description="附加信息")


class HealthReadyResponse(BaseModel):
    """就绪探针统一响应."""

    status: str = Field(..., description="整体状态: ready / not_ready")
    dependencies: dict[str, DependencyStatus] = Field(
        ..., description="各依赖状态详情"
    )
