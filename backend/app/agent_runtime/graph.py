"""LangGraph Agent 图定义."""

from __future__ import annotations

from functools import partial
from typing import Any

from langgraph.graph import END, StateGraph

from app.agent_runtime.nodes import classify_intent, execute_tool, extract_parameters, summarize
from app.agent_runtime.state import AgentState


def build_agent(tenant_id: str, user_id: str, db: Any = None) -> Any:
    """构建财务智能体状态图.

    流程：classify_intent -> extract_parameters -> execute_tool -> summarize -> END

    Args:
        tenant_id: 当前租户 ID，用于工具调用鉴权与数据隔离。
        user_id: 当前用户 ID，用于报告创建等需要用户身份的工具。
        db: 可选的数据库会话，用于测试注入。

    Returns:
        可执行的编译后状态图。
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("classify_intent", classify_intent)
    workflow.add_node("extract_parameters", extract_parameters)
    workflow.add_node(
        "execute_tool",
        partial(execute_tool, tenant_id=tenant_id, user_id=user_id, db=db),
    )
    workflow.add_node("summarize", summarize)

    workflow.set_entry_point("classify_intent")
    workflow.add_edge("classify_intent", "extract_parameters")
    workflow.add_edge("extract_parameters", "execute_tool")
    workflow.add_edge("execute_tool", "summarize")
    workflow.add_edge("summarize", END)

    return workflow.compile()


def run_agent(question: str, tenant_id: str, user_id: str, db: Any = None) -> dict[str, Any]:
    """一次性运行 Agent 并返回答案.

    Args:
        question: 用户自然语言问题。
        tenant_id: 租户 ID。
        user_id: 用户 ID。
        db: 可选的数据库会话，用于测试注入。

    Returns:
        Agent 最终状态，包含 answer、tool_result、intent 等字段。
    """
    agent = build_agent(tenant_id, user_id, db=db)
    initial_state: AgentState = {
        "question": question,
        "intent": None,
        "parameters": {},
        "tool_result": None,
        "answer": None,
        "error": None,
    }
    final_state = agent.invoke(initial_state)
    return dict(final_state)
