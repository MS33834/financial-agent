"""IM 机器人业务服务.

处理解析后的命令，调用后端业务能力，返回格式化文本。
MVP 阶段通过 HTTP Client 调用本机 API；后续可改为直接调用 service 层。
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.im.commands import (
    BotCommand,
    format_approval_result,
    format_nl2sql_result,
    format_report_result,
)


class IMServiceError(Exception):
    """IM 服务异常."""

    pass


def _call_api(method: str, path: str, token: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
    """内部调用后端 API.

    使用 TestClient 避免网络开销，实际生产环境应使用 httpx + 内网地址。
    为避免循环导入，在函数内部延迟导入 app.main.app。
    """
    from app.main import app

    headers = {"Authorization": f"Bearer {token}"}
    with TestClient(app) as client:
        if method == "GET":
            response = client.get(path, headers=headers)
        elif method == "POST":
            response = client.post(path, headers=headers, json=json)
        else:
            raise IMServiceError(f"Unsupported method: {method}")

    if response.status_code >= 400:
        raise IMServiceError(response.text)
    payload: dict[str, Any] = response.json()
    data: dict[str, Any] = payload.get("data", {})
    return data


def handle_command(command: BotCommand, token: str) -> str:
    """处理机器人命令.

    Args:
        command: 解析后的命令。
        token: 当前用户的 JWT Token。

    Returns:
        回复文本。
    """
    if command.name == "query":
        question = " ".join(command.args)
        if not question:
            return "请输入问题，例如：/query 2025年Q2营业收入"
        result = _call_api("POST", "/api/v1/queries/nl2sql", token, {"question": question})
        return format_nl2sql_result(result)

    if command.name == "report":
        report_type = command.args[0] if command.args else "profit"
        title = command.kwargs.get("title") or f"IM 创建报告 {report_type}"
        parameters = {k: v for k, v in command.kwargs.items() if k != "title"}
        result = _call_api(
            "POST",
            "/api/v1/reports",
            token,
            {"title": title, "report_type": report_type, "parameters": parameters},
        )
        return format_report_result(result)

    if command.name == "approve":
        report_id = command.kwargs.get("report_id")
        action = command.kwargs.get("action", "approve")
        comments = command.kwargs.get("comment") or command.kwargs.get("comments")
        if not report_id:
            return "请输入 report_id，例如：/approve report_id=xxx action=approve"
        result = _call_api(
            "POST",
            f"/api/v1/approvals/{report_id}/action",
            token,
            {"action": action, "comments": comments},
        )
        return format_approval_result({"success": True, "data": result})

    return f"未知命令：/{command.name}\n支持：/query、/report、/approve"
