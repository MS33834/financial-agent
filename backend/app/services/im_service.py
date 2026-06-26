"""IM 机器人业务服务.

处理解析后的命令，直接调用后端 service 层，返回格式化文本。
不再通过 TestClient/HTTP 调用内部 API，避免生产环境实例化 ASGI 应用。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.abac import ABACEngine
from app.core.roles import Role
from app.im.commands import (
    BotCommand,
    format_approval_result,
    format_nl2sql_result,
    format_report_result,
)
from app.models.access_policy import AccessPolicy
from app.models.user import User
from app.schemas.report import ReportCreate
from app.services.approval_service import ApprovalError, record_approval
from app.services.query_service import QueryService
from app.services.report_service import create_report_task, get_report, list_reports

# 每个 IM 用户最近查询的待审报告 ID 列表，支持 /approve 序号 快速审批
_pending_reports: dict[str, list[str]] = {}


class IMServiceError(Exception):
    """IM 服务异常."""

    pass


def _format_service_error(exc: Exception) -> str:
    """将 service 层异常转换为可操作的提示文本.

    根据常见业务错误给出针对性建议，避免将原始响应文本直接暴露给 IM 平台用户。
    """
    text = str(exc)
    if "权限" in text or "无权" in text:
        return "操作失败：当前用户权限不足，请联系管理员开通审批或查询权限。"
    if "不存在" in text or "未找到" in text:
        return "操作失败：未找到指定资源，请检查 report_id 是否正确。"
    if "仅 reviewing 状态的报告可执行审核" in text or "不处于待审核状态" in text:
        return "操作失败：该报告不处于待审核状态，无需审批。可通过 /pending 查看待审报告。"
    if "无效的审核动作" in text:
        return "操作失败：审核动作仅支持 approve（通过）、reject（驳回）、modify（退回修改）。"
    if "安全校验" in text:
        return f"操作失败：{text}"
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


def handle_command(command: BotCommand, db: Session, user: User) -> str:
    """处理机器人命令.

    Args:
        command: 解析后的命令。
        db: 数据库会话。
        user: 当前 IM 用户对应的系统用户。

    Returns:
        回复文本。
    """
    try:
        return _handle_command(command, db, user)
    except IMServiceError as exc:
        return _format_service_error(exc)


def _handle_command(command: BotCommand, db: Session, user: User) -> str:
    """实际命令处理逻辑."""
    if command.name == "query":
        question = " ".join(command.args)
        if not question:
            return "请输入问题，例如：/query 2025年Q2营业收入"
        service = QueryService()
        result = service.nl2sql(question, str(user.tenant_id), db, user=user)
        return format_nl2sql_result(result)

    if command.name == "report":
        report_type = command.args[0] if command.args else "profit"
        title = command.kwargs.get("title") or f"IM 创建报告 {report_type}"
        parameters = {k: v for k, v in command.kwargs.items() if k != "title"}
        data = ReportCreate(
            title=title,
            report_type=report_type,  # type: ignore[arg-type]
            parameters=parameters,
        )
        report = create_report_task(db=db, data=data, user=user)
        return format_report_result(
            {
                "report_id": report.id,
                "title": report.title,
                "status": report.status,
            }
        )

    if command.name in {"approve", "reject", "modify"}:
        # /approve 命令兼容 /reject、/modify 快捷语法
        report_id, error = _resolve_report_id_from_command(command, str(user.id))
        if error:
            return error
        assert report_id is not None

        if user.role not in {Role.ADMIN, Role.AUDITOR}:
            return "操作失败：当前用户权限不足，请联系管理员开通审批权限。"

        action = command.name if command.name != "approve" else command.kwargs.get("action", "approve")
        comments = command.kwargs.get("comment") or command.kwargs.get("comments")

        allowed, abac_error = _check_abac_approval_permission(user, report_id, db)
        if not allowed:
            return f"操作失败：{abac_error}"

        target_report = get_report(db, report_id, user.tenant_id)
        if target_report is None:
            return "操作失败：未找到指定报告，请检查 report_id 是否正确。"

        try:
            approval = record_approval(
                db=db,
                report=target_report,
                action=action,
                comments=comments,
                user=user,
            )
        except ApprovalError as exc:
            raise IMServiceError(str(exc)) from exc

        return format_approval_result(
            {
                "success": True,
                "data": {
                    "report_id": approval.report_id,
                    "action": approval.action,
                },
            }
        )

    if command.name == "pending":
        items, _total = list_reports(
            db=db,
            tenant_id=user.tenant_id,
            page=1,
            page_size=10,
            status="reviewing",
        )
        if not items:
            _pending_reports.pop(str(user.id), None)
            return "当前没有待审核的报告。"

        report_ids = [str(item.id) for item in items]
        _pending_reports[str(user.id)] = report_ids

        lines = ["待审核报告（可用 /approve 序号 快速审批，如 /approve 1）："]
        for idx, item in enumerate(items, 1):
            lines.append(
                f"{idx}. {item.title} | 类型：{item.report_type} | "
                f"ID：{str(item.id)[:8]}"
            )
        return "\n".join(lines)

    return f"未知命令：/{command.name}\n支持：/query、/report、/pending、/approve、/reject、/modify"
