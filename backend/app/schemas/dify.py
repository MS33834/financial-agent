"""Dify Tools API 相关 Schema."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class DifyToolBase(BaseModel):
    """Dify Tool 请求基础字段."""

    tenant_id: str = Field(description="租户 ID")
    user_id: str = Field(description="用户 ID（用于审计日志关联）")


class DifyNL2SQLRequest(DifyToolBase):
    """Dify NL2SQL Tool 请求."""

    question: str = Field(description="自然语言问题")


class DifyCreateReportRequest(DifyToolBase):
    """Dify 创建报告 Tool 请求."""

    title: str = Field(description="报告标题")
    report_type: Literal["profit", "balance", "cash", "custom"] = Field(
        default="profit", description="报告类型"
    )
    parameters: dict[str, Any] = Field(default_factory=dict, description="报告参数")


class DifyApproveReportRequest(DifyToolBase):
    """Dify 审批报告 Tool 请求."""

    report_id: str = Field(description="报告 ID")
    action: Literal["approve", "reject", "modify"] = Field(
        default="approve", description="approve/reject/modify"
    )
    comments: str | None = Field(default=None, description="审批意见")


class DifyParseDocumentRequest(DifyToolBase):
    """Dify 触发文档解析 Tool 请求."""

    document_id: str = Field(description="已上传文档 ID")


class DifyToolResponse(BaseModel):
    """Dify Tool 统一响应."""

    success: bool = Field(default=True, description="是否成功")
    data: dict[str, Any] = Field(default_factory=dict, description="业务数据")
    error: str | None = Field(default=None, description="错误信息")
