"""自然语言查询相关 Schema."""

from typing import Any

from pydantic import BaseModel, Field


class NLQueryRequest(BaseModel):
    """自然语言查询请求."""

    question: str = Field(description="自然语言问题", min_length=1)


class NLQueryResponse(BaseModel):
    """自然语言查询响应."""

    question: str = Field(description="原始问题")
    sql: str | None = Field(default=None, description="生成的 SQL")
    data: list[dict[str, Any]] = Field(default=[], description="查询结果")
    execution_time_ms: int | None = Field(default=None, description="执行耗时（毫秒）")
    confidence: float | None = Field(default=None, description="置信度")
    backend: str | None = Field(default=None, description="生成 SQL 的后端类型")
    explanation: str | None = Field(default=None, description="SQL 解释")
    error: str | None = Field(default=None, description="错误信息")
