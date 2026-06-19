"""解析记录清洗工具."""

from __future__ import annotations

import json
import re
from typing import Any


def clean_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """清洗解析出的记录列表.

    处理步骤：
    - 去除 key 为空字符串的列；
    - 对字符串值做 strip；
    - 将金额字符串中的人民币符号、逗号等去掉并尝试转为 float；
    - 去除完全为空（所有值均为空/None）的行；
    - 去除重复行（整行内容相同）。

    Args:
        records: 原始记录列表。

    Returns:
        清洗后的记录列表。
    """
    if not records:
        return []

    # 收集并保留非空 key 的列
    valid_keys = {key for record in records for key in record if key != ""}

    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()

    # 年份、周期等标识字段应保持原值，不被识别为金额
    _skip_amount_parse = {"year", "period"}

    for record in records:
        new_record: dict[str, Any] = {}
        for key, value in record.items():
            if key not in valid_keys:
                continue
            if isinstance(value, str):
                value = value.strip()
                if key not in _skip_amount_parse:
                    value = _try_parse_amount(value)
            new_record[key] = value

        # 跳过完全为空的行
        if _is_empty_record(new_record):
            continue

        # 去重：基于排序后的 JSON 签名
        signature = json.dumps(new_record, sort_keys=True, default=str)
        if signature in seen:
            continue
        seen.add(signature)
        cleaned.append(new_record)

    return cleaned


def _is_empty_record(record: dict[str, Any]) -> bool:
    """判断记录的所有值是否均为空/None."""
    return all(value is None or value == "" for value in record.values())


def _try_parse_amount(value: str) -> Any:
    """尝试将金额字符串转为 float，失败则返回原值.

    仅当原值包含人民币符号或千分位逗号时才进行转换，避免将年份、周期等字段误转。
    """
    has_amount_marker = any(ch in value for ch in ("¥", "￥", ",", "，"))
    if not has_amount_marker:
        return value
    cleaned = value.replace("¥", "").replace("￥", "").replace(",", "").replace("，", "").strip()
    if not cleaned:
        return value
    if re.fullmatch(r"^[+-]?\d+(\.\d+)?$", cleaned):
        try:
            return float(cleaned)
        except ValueError:
            return value
    return value


def calculate_confidence(
    original_count: int, cleaned_count: int, parse_confidence: float
) -> float:
    """根据清洗结果计算最终置信度.

    Args:
        original_count: 原始记录数。
        cleaned_count: 清洗后记录数。
        parse_confidence: parser 给出的基础置信度。

    Returns:
        0~1 之间的最终置信度。
    """
    confidence = parse_confidence
    if original_count > 0 and cleaned_count / original_count < 0.5:
        confidence *= 0.5
    return max(0.0, min(1.0, confidence))
