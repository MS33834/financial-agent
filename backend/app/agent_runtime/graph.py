"""LangGraph Agent 图定义."""

from __future__ import annotations

import time
from functools import partial
from typing import Any

from langgraph.graph import END, StateGraph

from app.agent_runtime.nodes import classify_intent, execute_tool, extract_parameters, summarize
from app.agent_runtime.state import AgentState
from app.logger import get_logger

logger = get_logger(__name__)

# 工具执行错误重试配置
_RETRY_MAX = 2
_RETRY_BASE_DELAY = 0.1


def _execute_tool_with_retry(
    state: AgentState,
    tenant_id: str,
    user_id: str,
    db: Any = None,
) -> AgentState:
    """execute_tool 的重试包装器.

    对工具执行错误（以 "工具执行失败" 开头）最多重试 2 次，采用指数退避。
    参数校验类错误（缺少参数、无法识别意图）不重试。

    Args:
        state: Agent 当前状态。
        tenant_id: 租户 ID。
        user_id: 用户 ID。
        db: 可选的数据库会话。

    Returns:
        更新后的 Agent 状态，携带 retry_count 字段。
    """
    # 从运行时 state 中读取重试计数（AgentState 在运行时携带该字段）
    state_dict: dict[str, Any] = dict(state)
    retry_count_raw = state_dict.get("retry_count", 0)
    retry_count = retry_count_raw if isinstance(retry_count_raw, int) else 0

    last_result: dict[str, Any] = dict(state)
    for attempt in range(_RETRY_MAX + 1):
        try:
            agent_result = execute_tool(state, tenant_id=tenant_id, user_id=user_id, db=db)
            last_result = dict(agent_result)
        except Exception as exc:  # noqa: BLE001
            last_result = {**state_dict, "error": f"工具执行失败: {exc!s}"}

        error = last_result.get("error")

        # 无错误或参数校验类错误，无需重试
        if not error or not str(error).startswith("工具执行失败"):
            break

        # 工具执行错误，判断是否可重试
        retry_count += 1
        if attempt < _RETRY_MAX:
            delay = _RETRY_BASE_DELAY * (2 ** attempt)
            time.sleep(delay)
            logger.warning(
                "execute_tool_retry",
                attempt=attempt + 1,
                max_retries=_RETRY_MAX,
                delay=delay,
                error=str(error),
            )
            continue

    last_result["retry_count"] = retry_count
    return last_result  # type: ignore[return-value]


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
        partial(_execute_tool_with_retry, tenant_id=tenant_id, user_id=user_id, db=db),
    )
    workflow.add_node("summarize", summarize)

    workflow.set_entry_point("classify_intent")
    workflow.add_edge("classify_intent", "extract_parameters")
    workflow.add_edge("extract_parameters", "execute_tool")
    workflow.add_edge("execute_tool", "summarize")
    workflow.add_edge("summarize", END)

    return workflow.compile()


def run_agent(
    question: str,
    tenant_id: str,
    user_id: str,
    db: Any = None,
    conversation_id: str | None = None,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """一次性运行 Agent 并返回答案.

    Args:
        question: 用户自然语言问题。
        tenant_id: 租户 ID。
        user_id: 用户 ID。
        db: 可选的数据库会话，用于测试注入。
        conversation_id: 对话 ID，用于多轮对话追踪。
        history: 历史对话消息列表，用于多轮上下文。

    Returns:
        Agent 最终状态，包含 answer、tool_result、intent 等字段。
    """
    agent = build_agent(tenant_id, user_id, db=db)
    initial_state: dict[str, Any] = {
        "question": question,
        "intent": None,
        "parameters": {},
        "tool_result": None,
        "answer": None,
        "error": None,
        "conversation_id": conversation_id,
        "messages": history or [],
        "retry_count": 0,
    }
    final_state = agent.invoke(initial_state)
    return dict(final_state)
