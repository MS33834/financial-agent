"""文档解析相关 Schema."""

from typing import Any

from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    """创建文档解析任务请求."""

    filename: str = Field(description="原始文件名")
    storage_key: str = Field(description="对象存储 key")


class DocumentResponse(BaseModel):
    """文档解析任务响应."""

    id: str = Field(description="任务 ID")
    filename: str = Field(description="原始文件名")
    status: str = Field(description="状态")
    confidence: float | None = Field(default=None, description="解析置信度")
    parse_result: dict[str, Any] | None = Field(default=None, description="解析结果")
    error_message: str | None = Field(default=None, description="错误信息")
    created_at: str = Field(description="创建时间")


class DocumentListItem(DocumentResponse):
    """文档列表项."""

    pass
