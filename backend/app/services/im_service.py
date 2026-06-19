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


def _format_api_error(exc: IMServiceError) -> str:
    """将 API 调用异常转换为可操作的提示文本.

    根据状态码与常见业务错误给出针对性建议，实现简单的错误自省。
    """
    text = str(exc)
    if "403" in text or "Permission denied" in text:
        return "操作失败：当前用户权限不足，请联系管理员开通审批或查询权限。"
    if "404" in text or "Report not found" in text:
        return "操作失败：未找到指定资源，请检查 report_id 是否正确。"
    if "仅 reviewing 状态的报告可执行审核" in text:
        return "操作失败：该报告不处于待审核状态，无需审批。可通过 /pending 查看待审报告。"
    if "无效的审核动作" in text:
        return "操作失败：审核动作仅支持 approve（通过）、reject（驳回）、modify（退回修改）。"
    return f"操作失败：{text}"


def handle_command(command: BotCommand, token: str) -> str:
    """处理机器人命令.

    Args:
        command: 解析后的命令。
        token: 当前用户的 JWT Token。

    Returns:
        回复文本。
    """
    try:
        return _handle_command(command, token)
    except IMServiceError as exc:
        return _format_api_error(exc)


def _handle_command(command: BotCommand, token: str) -> str:
    """实际命令处理逻辑."""
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

    if command.name in {"approve", "reject", "modify"}:
        # /approve 命令兼容 /reject、/modify 快捷语法
        report_id = command.kwargs.get("report_id") or (command.args[0] if command.args else "")
        action = command.name if command.name != "approve" else command.kwargs.get("action", "approve")
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

    if command.name == "pending":
        result = _call_api("GET", "/api/v1/reports?status=reviewing&page_size=10", token)
        items = result.get("items", [])
        if not items:
            return "当前没有待审核的报告。"
        lines = ["待审核报告："]
        for item in items:
            lines.append(f"- ID：{item.get('id')} | 标题：{item.get('title')} | 类型：{item.get('report_type')}")
        return "\n".join(lines)

    return f"未知命令：/{command.name}\n支持：/query、/report、/pending、/approve、/reject、/modify"
