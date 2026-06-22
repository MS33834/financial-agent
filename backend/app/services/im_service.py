"""IM 机器人业务服务.

处理解析后的命令，调用后端业务能力，返回格式化文本。
MVP 阶段通过 HTTP Client 调用本机 API；后续可改为直接调用 service 层。
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.abac import ABACEngine
from app.im.commands import (
    BotCommand,
    format_approval_result,
    format_nl2sql_result,
    format_report_result,
)
from app.models.access_policy import AccessPolicy
from app.models.user import User
from app.services.report_service import get_report

# 每个 IM 用户最近查询的待审报告 ID 列表，支持 /approve 序号 快速审批
_pending_reports: dict[str, list[str]] = {}


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
        detail = "服务内部错误"
        try:
            payload = response.json()
            detail = payload.get("message") or payload.get("detail") or detail
        except Exception:  # noqa: BLE001
            pass
        raise IMServiceError(f"[{response.status_code}] {detail}")
    response_payload: dict[str, Any] = response.json()
    data: dict[str, Any] = response_payload.get("data") or {}
    return data


def _format_api_error(exc: IMServiceError) -> str:
    """将 API 调用异常转换为可操作的提示文本.

    根据状态码与常见业务错误给出针对性建议，实现简单的错误自省。
    避免将原始响应文本直接暴露给 IM 平台用户。
    """
    text = str(exc)
    if "[403]" in text or "权限" in text:
        return "操作失败：当前用户权限不足，请联系管理员开通审批或查询权限。"
    if "[404]" in text or "不存在" in text:
        return "操作失败：未找到指定资源，请检查 report_id 是否正确。"
    if "仅 reviewing 状态的报告可执行审核" in text:
        return "操作失败：该报告不处于待审核状态，无需审批。可通过 /pending 查看待审报告。"
    if "无效的审核动作" in text:
        return "操作失败：审核动作仅支持 approve（通过）、reject（驳回）、modify（退回修改）。"
    if "[400]" in text:
        return "操作失败：请求参数有误，请检查命令格式。"
    if "[500]" in text:
        return "操作失败：服务暂时不可用，请稍后重试。"
    return "操作失败：服务处理异常，请稍后重试或联系管理员。"


def _resolve_report_id_from_command(
    command: BotCommand, user_id: str
) -> tuple[str | None, str | None]:
    """从命令中解析 report_id，支持序号引用最近 /pending 结果.

    Returns:
        (report_id, error_message)。解析失败时返回 (None, 错误提示)。
    """
    raw = command.kwargs.get("report_id") or (command.args[0] if command.args else "")
    if not raw:
        return None, "请输入 report_id 或序号，例如：/approve report_id=xxx 或 /approve 1"

    if raw.isdigit():
        index = int(raw) - 1
        cached = _pending_reports.get(user_id, [])
        if not cached:
            return None, "未找到待审报告缓存，请先执行 /pending 查看列表。"
        if index < 0 or index >= len(cached):
            return None, f"序号 {raw} 超出范围，当前 /pending 列表共 {len(cached)} 条。"
        return cached[index], None

    return raw, None


def _has_abac_policy_for_approval(user: User, db: Session) -> bool:
    """租户是否已配置 report/approve 的 ABAC 策略."""
    return (
        db.query(AccessPolicy)
        .filter(
            AccessPolicy.tenant_id == user.tenant_id,
            AccessPolicy.resource_type == "report",
            AccessPolicy.action == "approve",
            AccessPolicy.is_active.is_(True),
        )
        .first()
        is not None
    )


def _check_abac_approval_permission(
    user: User, report_id: str, db: Session
) -> tuple[bool, str | None]:
    """通过 ABAC 校验用户是否有权审批指定报告.

    若租户未配置 report/approve 的 ABAC 策略，则保持现有 RBAC 行为，
    避免默认拒绝影响已有审批流程。

    Returns:
        (是否允许, 错误提示)。
    """
    report = get_report(db, report_id, user.tenant_id)
    if report is None:
        return False, "未找到指定报告，请检查 report_id 是否正确。"

    if not _has_abac_policy_for_approval(user, db):
        return True, None

    engine = ABACEngine(db)
    allowed = engine.evaluate(
        user,
        "report",
        "approve",
        resource_attributes={
            "id": str(report.id),
            "report_type": report.report_type,
            "status": report.status,
            "created_by": report.created_by,
            "tenant_id": report.tenant_id,
        },
    )
    if not allowed:
        return False, "ABAC 策略拒绝此次审批，请联系管理员调整策略。"
    return True, None


def handle_command(command: BotCommand, token: str, db: Session, user: User) -> str:
    """处理机器人命令.

    Args:
        command: 解析后的命令。
        token: 当前用户的 JWT Token。
        db: 数据库会话。
        user: 当前 IM 用户对应的系统用户。

    Returns:
        回复文本。
    """
    try:
        return _handle_command(command, token, db, user)
    except IMServiceError as exc:
        return _format_api_error(exc)


def _handle_command(command: BotCommand, token: str, db: Session, user: User) -> str:
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
        report_id, error = _resolve_report_id_from_command(command, str(user.id))
        if error:
            return error
        assert report_id is not None

        action = command.name if command.name != "approve" else command.kwargs.get("action", "approve")
        comments = command.kwargs.get("comment") or command.kwargs.get("comments")

        allowed, abac_error = _check_abac_approval_permission(user, report_id, db)
        if not allowed:
            return f"操作失败：{abac_error}"

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
            _pending_reports.pop(str(user.id), None)
            return "当前没有待审核的报告。"

        report_ids = [str(item.get("id")) for item in items if item.get("id")]
        _pending_reports[str(user.id)] = report_ids

        lines = ["待审核报告（可用 /approve 序号 快速审批，如 /approve 1）："]
        for idx, item in enumerate(items, 1):
            lines.append(
                f"{idx}. {item.get('title')} | 类型：{item.get('report_type')} | "
                f"ID：{str(item.get('id'))[:8]}"
            )
        return "\n".join(lines)

    return f"未知命令：/{command.name}\n支持：/query、/report、/pending、/approve、/reject、/modify"
