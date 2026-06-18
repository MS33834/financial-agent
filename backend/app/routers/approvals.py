"""人工审核路由."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.user import User
from app.schemas.approval import ApprovalAction, ApprovalResponse
from app.schemas.common import DataResponse
from app.services.report_service import get_report, update_report_status

router = APIRouter(prefix="/api/v1/approvals", tags=["Approvals"])


@router.post("/{report_id}/action", response_model=DataResponse[ApprovalResponse])
def approval_action(
    report_id: str,
    action_data: ApprovalAction,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """对报告执行审核操作."""
    report = get_report(db=db, report_id=report_id, tenant_id=user.tenant_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    action = action_data.action.lower()
    if action == "approve":
        new_status = "approved"
    elif action == "reject":
        new_status = "rejected"
    elif action == "modify":
        new_status = "draft"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid action",
        )

    update_report_status(db=db, report=report, status=new_status)

    return {
        "code": 0,
        "message": "ok",
        "data": {
            "id": "approval-placeholder",
            "report_id": report_id,
            "reviewer_id": user.id,
            "action": action,
            "comments": action_data.comments,
            "created_at": datetime.now(UTC).isoformat(),
        },
    }
