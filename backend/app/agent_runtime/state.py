"""LangGraph Agent 状态定义."""

from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    """Agent 执行过程中的共享状态.

    Attributes:
        question: 用户原始自然语言问题。
        intent: 识别后的意图（nl2sql/create_report/parse_document/document_qa/unknown）。
        parameters: 从问题中提取的结构化参数。
        tool_result: 工具执行结果。
        answer: 最终自然语言回答。
        error: 执行过程中的错误信息。
    """

    question: str
    intent: str | None
    parameters: dict[str, Any]
    tool_result: dict[str, Any] | None
    answer: str | None
    error: str | None
