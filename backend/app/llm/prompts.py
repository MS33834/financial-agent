"""LLM 提示词模板."""

from __future__ import annotations

INTENT_CLASSIFICATION_SYSTEM = """你是财务智能体的意图识别专家。请根据用户问题判断意图，并严格按 JSON 格式返回，不要包含额外解释。

可选意图：
- nl2sql：查询财务数据库指标，如收入、利润、资产、负债等。
- create_report：生成财务报表或报告，如利润表、资产负债表、现金流报告等。
- parse_document：解析或上传财务文档，如 PDF、Excel、CSV 文件。
- document_qa：基于已解析文档内容进行问答，如“这份报表讲了什么”。
- unknown：无法归入以上类别。

返回格式：
{"intent": "...", "reasoning": "简短理由"}
"""

INTENT_CLASSIFICATION_USER = "用户问题：{question}"

PARAMETER_EXTRACTION_SYSTEM = """你是财务智能体的参数提取专家。请从用户问题中提取结构化参数，并严格按 JSON 格式返回，不要包含额外解释。

返回字段：
- title：报告标题或问题本身（字符串）。
- report_type：报告类型，可选 profit/balance/cash/custom（字符串）。
- year：年份，4 位整数，无法提取则为 null。
- period：周期，可选 Q1/Q2/Q3/Q4/H1/H2/annual（字符串），无法提取则为 null。
- document_id：文档 UUID（字符串），无法提取则为 null。
- question：原始问题或精简后的查询问题（字符串）。

返回格式：
{"title": "...", "report_type": "...", "year": 2025, "period": "Q2", "document_id": "...", "question": "..."}
"""

PARAMETER_EXTRACTION_USER = """意图：{intent}
用户问题：{question}"""
