"""人工审核路由."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.roles import Role
from app.database import get_db
from app.dependencies import require_role
from app.models.approval import Approval
from app.models.report import Report
from app.models.user import User
from app.schemas.approval import ApprovalAction, ApprovalResponse
from app.schemas.common import DataResponse
from app.services.approval_service import ApprovalError, record_approval
from app.services.report_service import get_report

router = APIRouter(prefix="/api/v1/approvals", tags=["Approvals"])


def _to_approval_response(approval: Approval) -> dict[str, Any]:
    """将 Approval ORM 对象转为响应字典."""
    return {
        "id": approval.id,
        "report_id": approval.report_id,
        "reviewer_id": approval.reviewer_id,
        "action": approval.action,
        "comments": approval.comments,
        "created_at": approval.created_at.isoformat() if approval.created_at else None,
    }


@router.get("", response_model=DataResponse[list[ApprovalResponse]])
def list_approvals(
    report_id: str | None = Query(default=None, description="按报告 ID 筛选"),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.AUDITOR)),
) -> dict[str, Any]:
    """查询人工审核记录列表（仅管理员/审计员）."""
    query = (
        db.query(Approval)
        .join(Report, Approval.report_id == Report.id)
        .filter(Report.tenant_id == user.tenant_id)
    )
    if report_id:
        query = query.filter(Approval.report_id == report_id)

    approvals = query.order_by(Approval.created_at.desc()).all()
    return {
        "code": 0,
        "message": "ok",
        "data": [_to_approval_response(approval) for approval in approvals],
    }


@router.post("/{report_id}/action", response_model=DataResponse[ApprovalResponse])
def approval_action(
    report_id: str,
    action_data: ApprovalAction,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.AUDITOR)),
) -> dict[str, Any]:
    """对报告执行审核操作."""
    report = get_report(db=db, report_id=report_id, tenant_id=user.tenant_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    try:
        approval = record_approval(
            db=db,
            report=report,
            action=action_data.action,
            comments=action_data.comments,
            user=user,
        )
    except ApprovalError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return {
        "code": 0,
        "message": "ok",
        "data": _to_approval_response(approval),
    }
