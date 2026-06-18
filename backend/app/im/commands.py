"""IM 机器人命令解析器.

支持命令：
- /query 2025年Q2营业收入
- /report profit year=2025 period=Q2
- /approve report_id=xxx action=approve comment=同意
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class BotCommand:
    """解析后的机器人命令."""

    name: str
    args: list[str]
    kwargs: dict[str, str]


def parse_command(text: str) -> BotCommand:
    """解析文本命令.

    Args:
        text: 用户输入文本，如 ``/report profit year=2025``。

    Returns:
        BotCommand 对象。

    Raises:
        ValueError: 文本不是有效命令。
    """
    text = text.strip()
    if not text.startswith("/"):
        raise ValueError("命令需以 / 开头")

    parts = text.split()
    name = parts[0][1:]  # 去掉 /
    args: list[str] = []
    kwargs: dict[str, str] = {}

    for part in parts[1:]:
        match = re.match(r"^(\w+)=(.+)$", part)
        if match:
            kwargs[match.group(1)] = match.group(2)
        else:
            args.append(part)

    return BotCommand(name=name, args=args, kwargs=kwargs)


def format_nl2sql_result(result: dict[str, Any]) -> str:
    """格式化 NL2SQL 结果为可读文本."""
    if error := result.get("error"):
        return f"查询失败：{error}"

    question = result.get("question", "")
    data = result.get("data", [])
    if not data:
        return f"问题：{question}\n未查询到数据。"

    lines = [f"问题：{question}", "结果："]
    for row in data:
        lines.append(str(row))
    return "\n".join(lines)


def format_report_result(report: dict[str, Any]) -> str:
    """格式化报告创建结果."""
    return (
        f"报告已创建\n"
        f"ID：{report.get('report_id')}\n"
        f"标题：{report.get('title')}\n"
        f"状态：{report.get('status')}"
    )


def format_approval_result(result: dict[str, Any]) -> str:
    """格式化审批结果."""
    if not result.get("success"):
        return f"审批失败：{result.get('error')}"
    data = result.get("data", {})
    return f"审批完成\n报告 ID：{data.get('report_id')}\n动作：{data.get('action')}"
