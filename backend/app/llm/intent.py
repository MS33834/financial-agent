"""基于 LLM 的意图识别与参数提取."""

from __future__ import annotations

import json
import re
from typing import Any, cast

from app.llm.client import LLMClient
from app.llm.prompts import (
    INTENT_CLASSIFICATION_SYSTEM,
    INTENT_CLASSIFICATION_USER,
    PARAMETER_EXTRACTION_SYSTEM,
    PARAMETER_EXTRACTION_USER,
)

VALID_INTENTS = {
    "nl2sql",
    "create_report",
    "parse_document",
    "document_qa",
    "unknown",
}


def _extract_json(text: str) -> dict[str, Any]:
    """从模型输出中提取 JSON，兼容 markdown 代码块."""
    text = text.strip()
    # 尝试匹配 ```json ... ``` 代码块
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        text = match.group(1).strip()
    # 如果整段不是 JSON，尝试提取第一个 { ... }
    if not text.startswith("{"):
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            text = match.group(0)
    return cast(dict[str, Any], json.loads(text))


def classify_intent_llm(question: str) -> dict[str, str]:
    """使用 LLM 识别用户意图.

    Args:
        question: 用户自然语言问题。

    Returns:
        {"intent": "...", "reasoning": "..."}

    Raises:
        LLMUnavailableError: LLM 不可用时抛出。
        ValueError: 返回无效 intent 时抛出。
    """
    client = LLMClient()
    content = client.chat(
        system_prompt=INTENT_CLASSIFICATION_SYSTEM,
        user_prompt=INTENT_CLASSIFICATION_USER.format(question=question),
    )
    result = _extract_json(content)
    intent = result.get("intent", "unknown")
    if intent not in VALID_INTENTS:
        raise ValueError(f"LLM 返回无效意图: {intent}")
    return {
        "intent": intent,
        "reasoning": str(result.get("reasoning", "")),
    }


def extract_parameters_llm(question: str, intent: str) -> dict[str, Any]:
    """使用 LLM 提取结构化参数.

    Args:
        question: 用户自然语言问题。
        intent: 识别出的意图。

    Returns:
        {"title": ..., "report_type": ..., "year": ..., "period": ..., "document_id": ..., "question": ...}

    Raises:
        LLMUnavailableError: LLM 不可用时抛出。
    """
    client = LLMClient()
    content = client.chat(
        system_prompt=PARAMETER_EXTRACTION_SYSTEM,
        user_prompt=PARAMETER_EXTRACTION_USER.format(question=question, intent=intent),
    )
    result = _extract_json(content)
    year = result.get("year")
    if year is not None:
        try:
            year = int(year)
        except (TypeError, ValueError):
            year = None
    return {
        "title": result.get("title") or question,
        "report_type": result.get("report_type") or "custom",
        "year": year,
        "period": result.get("period"),
        "document_id": result.get("document_id"),
        "question": result.get("question") or question,
    }
