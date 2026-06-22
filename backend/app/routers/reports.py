"""报告生成路由."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.roles import Role
from app.database import get_db
from app.dependencies import (
    get_current_user_or_api_key,
    get_pagination,
    require_role_or_api_key_scope,
)
from app.models.user import User
from app.schemas.common import DataResponse, PaginatedResponse, PaginationParams
from app.schemas.report import ReportCreate, ReportExportResponse, ReportResponse
from app.services.export_service import ExportFormatError, export_report
from app.services.report_service import create_report_task, get_report, list_reports
from app.storage import StorageClientError, get_storage_client

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
    user: User = Depends(get_current_user_or_api_key(scope="reports:write")),
) -> dict[str, Any]:
    """创建报告生成任务."""
    report = create_report_task(db=db, data=data, user=user)
    return {"code": 0, "message": "ok", "data": _to_report_response(report)}


@router.get("", response_model=PaginatedResponse[ReportResponse])
def list_reports_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_api_key(scope="reports:read")),
    pagination: PaginationParams = Depends(get_pagination),
    status: str | None = Query(default=None, description="按报告状态筛选"),
) -> dict[str, Any]:
    """查询报告列表."""
    items, total = list_reports(
        db=db,
        tenant_id=user.tenant_id,
        page=pagination.page,
        page_size=pagination.page_size,
        status=status,
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
    user: User = Depends(get_current_user_or_api_key(scope="reports:read")),
) -> dict[str, Any]:
    """获取单个报告."""
    report = get_report(db=db, report_id=report_id, tenant_id=user.tenant_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="报告不存在",
        )
    return {"code": 0, "message": "ok", "data": _to_report_response(report)}


@router.post("/{report_id}/export", response_model=DataResponse[ReportExportResponse])
def export_report_api(
    report_id: str,
    fmt: str = Query(default="markdown", alias="format", description="导出格式: markdown/json/pdf/xlsx"),
    db: Session = Depends(get_db),
    user: User = Depends(
        require_role_or_api_key_scope(
            Role.ADMIN,
            Role.FINANCE_MANAGER,
            Role.AUDITOR,
            scope="reports:export",
        )
    ),
) -> dict[str, Any]:
    """导出报告到对象存储."""
    report = get_report(db=db, report_id=report_id, tenant_id=user.tenant_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="报告不存在",
        )

    if report.status not in ("reviewing", "approved"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只有 reviewing 或 approved 状态的报告可导出",
        )

    try:
        url = export_report(
            db=db,
            report=report,
            storage=get_storage_client(),
            user=user,
            fmt=fmt,
        )
    except ExportFormatError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except StorageClientError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="导出文件上传失败，请稍后重试",
        ) from None

    db.commit()
    db.refresh(report)

    return {
        "code": 0,
        "message": "ok",
        "data": {"content_url": url, "format": fmt},
    }
