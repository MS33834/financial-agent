"""人工审核路由."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.roles import Role
from app.database import get_db
from app.dependencies import require_role
from app.models.user import User
from app.schemas.approval import ApprovalAction, ApprovalResponse
from app.schemas.common import DataResponse
from app.services.approval_service import ApprovalError, record_approval
from app.services.report_service import get_report

router = APIRouter(prefix="/api/v1/approvals", tags=["Approvals"])


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
        "data": {
            "id": approval.id,
            "report_id": approval.report_id,
            "reviewer_id": approval.reviewer_id,
            "action": approval.action,
            "comments": approval.comments,
            "created_at": approval.created_at.isoformat() if approval.created_at else None,
        },
    }
