"""LangGraph Agent 节点函数."""

from __future__ import annotations

import re
from typing import Any

from app.agent_runtime.state import AgentState
from app.agent_runtime.tools import (
    create_report_tool,
    document_qa_tool,
    nl2sql_tool,
    parse_document_tool,
)
from app.config import get_settings
from app.llm import LLMUnavailableError, classify_intent_llm, extract_parameters_llm
from app.logger import get_logger
from app.models.user import User

logger = get_logger(__name__)


class AgentRuntimeError(Exception):
    """Agent 节点执行异常."""

    pass


def classify_intent(state: AgentState) -> AgentState:
    """意图识别节点.

    当配置 agent_intent_mode=llm 时优先使用 LLM，失败或返回无效意图时降级到规则逻辑。
    """
    question = state.get("question", "").lower().strip()
    if not question:
        return {**state, "intent": "unknown", "error": "Empty question"}

    settings = get_settings()
    if settings.agent_intent_mode == "llm":
        try:
            result = classify_intent_llm(question)
            intent = result.get("intent", "unknown")
            if intent in {"nl2sql", "create_report", "parse_document", "document_qa", "unknown"}:
                return {**state, "intent": intent}
            logger.warning("llm_intent_invalid_fallback_to_rule", intent=intent)
        except (LLMUnavailableError, ValueError) as exc:
            logger.warning("llm_intent_failed_fallback_to_rule", error=str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.warning("llm_intent_unexpected_error", error=str(exc))

    return {**state, "intent": _classify_intent_by_rule(question)}


def _classify_intent_by_rule(question: str) -> str:
    """基于关键词做简单意图识别."""
    # 报告相关关键词
    report_keywords = ("报告", "生成报告", "利润表", "资产负债表", "现金流", "报表")
    # 文档问答相关关键词（在“文档”之前判断，避免“这份文档讲了什么”被误判为解析）
    qa_keywords = ("问答", "文档内容", "讲了什么", "总结一下", "摘要", "这份文档")
    # 文档解析相关关键词
    document_keywords = ("解析", "上传", "pdf", "excel", "文件")

    # 优先识别报告/文档动作意图，避免“生成利润表”被误判为查询
    if any(keyword in question for keyword in report_keywords):
        return "create_report"
    if any(keyword in question for keyword in qa_keywords):
        return "document_qa"
    if any(keyword in question for keyword in document_keywords):
        return "parse_document"
    if any(keyword in question for keyword in ("多少", "查询", "查", "收入", "利润", "资产", "负债")):
        return "nl2sql"

    return "unknown"


def extract_parameters(state: AgentState) -> AgentState:
    """根据意图提取结构化参数.

    当配置 agent_intent_mode=llm 时优先使用 LLM，失败时降级到原有正则提取。
    """
    intent = state.get("intent")
    question = state.get("question", "")
    parameters: dict[str, Any] = {}

    settings = get_settings()
    if settings.agent_intent_mode == "llm" and intent:
        try:
            parameters = extract_parameters_llm(question, intent)
            return {**state, "parameters": parameters}
        except LLMUnavailableError as exc:
            logger.warning("llm_parameters_failed_fallback_to_rule", error=str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.warning("llm_parameters_unexpected_error", error=str(exc))

    if intent == "nl2sql":
        parameters["question"] = question
    elif intent == "create_report":
        parameters["title"] = question or "自动生成的财务报告"
        parameters["report_type"] = _extract_report_type(question)
        parameters["year"] = _extract_year(question)
        parameters["period"] = _extract_period(question)
    elif intent == "parse_document":
        # 文档 ID 需要调用方显式提供，这里仅做占位
        parameters["document_id"] = _extract_document_id(question)
    elif intent == "document_qa":
        parameters["question"] = question
        parameters["document_id"] = _extract_document_id(question)

    return {**state, "parameters": parameters}


def execute_tool(
    state: AgentState, tenant_id: str, user_id: str, db: Any = None
) -> AgentState:
    """根据意图调用对应业务工具."""
    intent = state.get("intent")
    parameters = state.get("parameters", {})

    user: User | None = None
    if db is not None:
        user = db.query(User).filter(User.id == user_id, User.tenant_id == tenant_id).first()

    try:
        if intent == "nl2sql":
            result = nl2sql_tool(
                parameters.get("question", state.get("question", "")),
                tenant_id,
                db=db,
                user=user,
            )
        elif intent == "create_report":
            result = create_report_tool(
                title=parameters.get("title", "财务报告"),
                report_type=parameters.get("report_type", "profit"),
                parameters={"year": parameters.get("year"), "period": parameters.get("period")},
                tenant_id=tenant_id,
                user_id=user_id,
                db=db,
            )
        elif intent == "parse_document":
            doc_id = parameters.get("document_id")
            if not doc_id:
                return {**state, "error": "缺少 document_id 参数"}
            result = parse_document_tool(doc_id)
        elif intent == "document_qa":
            result = document_qa_tool(
                question=parameters.get("question", state.get("question", "")),
                tenant_id=tenant_id,
                document_id=parameters.get("document_id"),
                db=db,
            )
        else:
            return {**state, "error": "无法识别的问题意图"}
    except Exception as exc:  # noqa: BLE001
        return {**state, "error": f"工具执行失败: {exc!s}"}

    return {**state, "tool_result": result}


def summarize(state: AgentState) -> AgentState:
    """将工具结果整理为自然语言回答."""
    result = state.get("tool_result")
    error = state.get("error")
    intent = state.get("intent")

    if error:
        return {**state, "answer": f"处理失败：{error}"}

    if result is None:
        return {**state, "answer": "未获取到结果。"}

    if intent == "nl2sql":
        data = result.get("data", [])
        if not data:
            return {**state, "answer": "未查询到相关数据。"}
        # 取第一行结果生成自然语言描述
        row = data[0]
        parts = [f"{key}: {value}" for key, value in row.items()]
        return {**state, "answer": "查询结果：" + "，".join(parts)}

    if intent == "create_report":
        return {
            **state,
            "answer": f"报告《{result.get('title')}》已创建，当前状态：{result.get('status')}，ID：{result.get('report_id')}",
        }

    if intent == "parse_document":
        return {
            **state,
            "answer": f"文档解析任务已提交，任务 ID：{result.get('task_id')}",
        }

    if intent == "document_qa":
        answer = result.get("answer") or "未找到相关答案。"
        chunks = result.get("chunks", [])
        if chunks:
            answer += "\n\n参考片段：\n" + "\n---\n".join(chunks)
        return {**state, "answer": answer}

    return {**state, "answer": "已处理完成。"}


def _extract_year(question: str) -> int | None:
    """提取 4 位年份."""
    match = re.search(r"(?<!\d)(20\d{2})(?!\d)", question)
    return int(match.group(1)) if match else None


def _extract_period(question: str) -> str | None:
    """提取周期标识."""
    lowered = question.lower()
    period_map = {
        "q1": "Q1",
        "一季度": "Q1",
        "q2": "Q2",
        "二季度": "Q2",
        "q3": "Q3",
        "三季度": "Q3",
        "q4": "Q4",
        "四季度": "Q4",
        "上半年": "H1",
        "下半年": "H2",
        "全年": "annual",
        "年度": "annual",
    }
    for key, value in period_map.items():
        if key in lowered:
            return value
    return None


def _extract_report_type(question: str) -> str:
    """根据关键词推断报告类型."""
    lowered = question.lower()
    if "资产负债" in lowered or "资产" in lowered or "负债" in lowered:
        return "balance"
    if "现金流" in lowered or "现金" in lowered:
        return "cash"
    if "利润" in lowered or "损益" in lowered or "营收" in lowered:
        return "profit"
    return "custom"


def _extract_document_id(question: str) -> str | None:
    """尝试从问题中提取文档 ID（UUID 格式）."""
    match = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", question, re.IGNORECASE)
    return match.group(0) if match else None
