"""人工审核相关 Schema."""

from typing import Literal

from pydantic import BaseModel, Field


class ApprovalAction(BaseModel):
    """审核操作请求."""

    action: Literal["approve", "reject", "modify"] = Field(description="操作: approve/reject/modify")
    comments: str | None = Field(default=None, description="审核意见")


class ApprovalResponse(BaseModel):
    """审核记录响应."""

    id: str = Field(description="记录 ID")
    report_id: str = Field(description="报告 ID")
    reviewer_id: str | None = Field(default=None, description="审核人 ID")
    action: str = Field(description="操作")
    comments: str | None = Field(default=None, description="审核意见")
    created_at: str = Field(description="创建时间")
