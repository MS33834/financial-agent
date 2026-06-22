"""人工审核服务."""

from contextlib import suppress

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.approval import Approval
from app.models.report import Report
from app.models.user import User
from app.services.audit_service import log_action
from app.services.report_service import update_report_status


class ApprovalError(Exception):
    """审核业务异常."""

    pass


def _status_for_action(action: str) -> str:
    """根据审核动作返回目标报告状态."""
    mapping = {
        "approve": "approved",
        "reject": "rejected",
        "modify": "draft",
    }
    status = mapping.get(action)
    if status is None:
        raise ApprovalError(f"无效的审核动作: {action}")
    return status


def record_approval(
    db: Session,
    report: Report,
    action: str,
    comments: str | None,
    user: User,
) -> Approval:
    """记录审核操作并更新报告状态.

    Args:
        db: 数据库会话。
        report: 被审核的报告。
        action: 审核动作（approve/reject/modify）。
        comments: 审核意见。
        user: 审核人。

    Returns:
        创建的审核记录。

    Raises:
        ApprovalError: 动作无效或报告状态不允许审核时抛出。
    """
    action = action.lower()
    new_status = _status_for_action(action)

    if report.status != "reviewing":
        raise ApprovalError(f"当前报告状态为 {report.status}，仅 reviewing 状态的报告可执行审核")

    approval = Approval(
        report_id=report.id,
        reviewer_id=user.id,
        action=action,
        comments=comments,
    )
    db.add(approval)

    update_report_status(db=db, report=report, status=new_status)

    log_action(
        db=db,
        action=f"report.approval.{action}",
        resource=f"report://{report.id}",
        user=user,
        result=new_status,
        reason=comments,
    )

    db.commit()
    db.refresh(approval)

    with suppress(Exception):
        from app.metrics import FA_BUSINESS_OPERATIONS_TOTAL

        FA_BUSINESS_OPERATIONS_TOTAL.labels(operation=f"approval_{action}").inc()

    return approval


def handle_approval_error(error: ApprovalError) -> HTTPException:
    """将审核业务异常转换为 HTTP 400 响应."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(error),
    )
