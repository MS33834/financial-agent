"""报告生成相关 Schema."""

from typing import Any

from pydantic import BaseModel, Field


class ReportCreate(BaseModel):
    """创建报告请求."""

    title: str = Field(description="报告标题", min_length=1)
    report_type: str = Field(description="报告类型")
    parameters: dict[str, Any] = Field(default={}, description="报告参数")


class ReportResponse(BaseModel):
    """报告响应."""

    id: str = Field(description="报告 ID")
    title: str = Field(description="报告标题")
    report_type: str = Field(description="报告类型")
    status: str = Field(description="状态")
    parameters: dict[str, Any] = Field(description="报告参数")
    content: dict[str, Any] | None = Field(default=None, description="报告内容")
    content_url: str | None = Field(default=None, description="导出文件地址")
    summary: str | None = Field(default=None, description="摘要")
    error_message: str | None = Field(default=None, description="生成错误信息")
    created_at: str = Field(description="创建时间")


class ReportListItem(ReportResponse):
    """报告列表项."""

    pass
