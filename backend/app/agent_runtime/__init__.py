"""LangGraph Agent 运行时.

提供基于状态机的财务智能体：意图识别 -> 工具选择 -> 执行 -> 总结。
MVP 阶段内置 NL2SQL、报告创建、文档解析三种工具，便于 Dify 或前端直接调用。
"""

from __future__ import annotations

from app.agent_runtime.graph import build_agent
from app.agent_runtime.state import AgentState

__all__ = ["AgentState", "build_agent"]
