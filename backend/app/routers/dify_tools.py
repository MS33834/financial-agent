"""Dify Tools API.

供 Dify Workflow 通过 HTTP Request 节点调用后端业务能力。
所有接口使用 ``X-API-Key`` 做服务间认证，请求体中需携带 ``tenant_id`` 与 ``user_id``。
"""

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_dify_api_key
from app.models.user import User
from app.schemas.dify import (
    DifyApproveReportRequest,
    DifyCreateReportRequest,
    DifyNL2SQLRequest,
    DifyParseDocumentRequest,
    DifyToolResponse,
)
from app.services.approval_service import ApprovalError, record_approval
from app.services.query_service import QueryService
from app.services.report_service import create_report_task, get_report
from app.tasks.document_tasks import parse_document_task

router = APIRouter(prefix="/api/v1/dify/tools", tags=["Dify Tools"])


def _get_system_user(db: Session, tenant_id: str, user_id: str) -> User:
    """按请求中的 tenant_id/user_id 获取用户，用于服务层鉴权与审计.

    注意：此处 trust Dify 已完成的身份校验，后端只做存在性检查。
    """
    user = db.query(User).filter(User.id == user_id, User.tenant_id == tenant_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


@router.post("/nl2sql", response_model=DifyToolResponse)
def dify_nl2sql(
    request: DifyNL2SQLRequest,
    db: Session = Depends(get_db),
    _api_key: str = Depends(require_dify_api_key),
) -> dict[str, Any]:
    """自然语言转 SQL 查询 Tool."""
    user = _get_system_user(db, request.tenant_id, request.user_id)
    result = QueryService().nl2sql(request.question, str(user.tenant_id), db, user=user)
    return {
        "success": result.get("error") is None,
        "data": result,
        "error": result.get("error"),
    }


@router.post("/create_report", response_model=DifyToolResponse)
def dify_create_report(
    request: DifyCreateReportRequest,
    db: Session = Depends(get_db),
    _api_key: str = Depends(require_dify_api_key),
) -> dict[str, Any]:
    """创建财务报告 Tool."""
    from app.schemas.report import ReportCreate

    valid_report_type: Literal["profit", "balance", "cash", "custom"] = request.report_type  # type: ignore[assignment]

    user = _get_system_user(db, request.tenant_id, request.user_id)
    data = ReportCreate(
        title=request.title,
        report_type=valid_report_type,
        parameters=request.parameters,
    )
    report = create_report_task(db=db, data=data, user=user)
    return {
        "success": True,
        "data": {
            "report_id": report.id,
            "status": report.status,
            "title": report.title,
        },
    }


@router.post("/approve_report", response_model=DifyToolResponse)
def dify_approve_report(
    request: DifyApproveReportRequest,
    db: Session = Depends(get_db),
    _api_key: str = Depends(require_dify_api_key),
) -> dict[str, Any]:
    """审批报告 Tool."""
    user = _get_system_user(db, request.tenant_id, request.user_id)
    report = get_report(db=db, report_id=request.report_id, tenant_id=user.tenant_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    try:
        approval = record_approval(
            db=db,
            report=report,
            action=request.action,
            comments=request.comments,
            user=user,
        )
    except ApprovalError as exc:
        return {
            "success": False,
            "data": {"report_id": request.report_id, "status": report.status},
            "error": str(exc),
        }

    return {
        "success": True,
        "data": {
            "report_id": report.id,
            "status": report.status,
            "approval_id": approval.id,
            "action": approval.action,
        },
    }


@router.post("/parse_document", response_model=DifyToolResponse)
def dify_parse_document(
    request: DifyParseDocumentRequest,
    db: Session = Depends(get_db),
    _api_key: str = Depends(require_dify_api_key),
) -> dict[str, Any]:
    """触发文档解析任务 Tool（异步）."""
    # 校验文档归属，防止越权触发任意租户的文档解析
    from app.models.document import Document

    doc = db.query(Document).filter(Document.id == request.document_id).first()
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    user = _get_system_user(db, request.tenant_id, request.user_id)
    if doc.tenant_id != user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Document does not belong to the tenant",
        )

    task = parse_document_task.delay(request.document_id)
    return {
        "success": True,
        "data": {
            "document_id": request.document_id,
            "task_id": task.id,
        },
    }
