"""报告生成路由."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_active_user, get_pagination
from app.models.user import User
from app.schemas.common import DataResponse, PaginatedResponse, PaginationParams
from app.schemas.report import ReportCreate, ReportResponse
from app.services.report_service import create_report_task, get_report, list_reports

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])


def _to_report_response(report: Any) -> dict[str, Any]:
    """将 ORM 对象转为响应字典."""
    return {
        "id": report.id,
        "title": report.title,
        "report_type": report.report_type,
        "status": report.status,
        "parameters": report.parameters,
        "content": report.content,
        "content_url": report.content_url,
        "summary": report.summary,
        "error_message": report.error_message,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


@router.post("", response_model=DataResponse[ReportResponse], status_code=status.HTTP_201_CREATED)
def create_report(
    data: ReportCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """创建报告生成任务."""
    report = create_report_task(db=db, data=data, user=user)
    return {"code": 0, "message": "ok", "data": _to_report_response(report)}


@router.get("", response_model=PaginatedResponse[ReportResponse])
def list_reports_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
    pagination: PaginationParams = Depends(get_pagination),
) -> dict[str, Any]:
    """查询报告列表."""
    items, total = list_reports(
        db=db,
        tenant_id=user.tenant_id,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "total": total,
            "page": pagination.page,
            "page_size": pagination.page_size,
            "items": [_to_report_response(r) for r in items],
        },
    }


@router.get("/{report_id}", response_model=DataResponse[ReportResponse])
def get_report_api(
    report_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """获取单个报告."""
    report = get_report(db=db, report_id=report_id, tenant_id=user.tenant_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )
    return {"code": 0, "message": "ok", "data": _to_report_response(report)}
