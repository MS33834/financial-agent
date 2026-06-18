"""审计日志路由."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_pagination, require_role
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogResponse
from app.schemas.common import PaginatedResponse, PaginationParams

router = APIRouter(prefix="/api/v1/audit", tags=["Audit"])


def _to_audit_response(log: Any) -> dict[str, Any]:
    """将 ORM 对象转为响应字典."""
    return {
        "id": log.id,
        "timestamp": log.created_at.isoformat() if log.created_at else None,
        "tenant_id": log.tenant_id,
        "user_id": log.user_id,
        "action": log.action,
        "resource": log.resource,
        "result": log.result,
        "ip": log.ip,
        "reason": log.reason,
    }


@router.get("/logs", response_model=PaginatedResponse[AuditLogResponse])
def list_audit_logs(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "auditor")),
    pagination: PaginationParams = Depends(get_pagination),
) -> dict[str, Any]:
    """查询审计日志（仅管理员/审计员）."""
    query = db.query(AuditLog).filter(AuditLog.tenant_id == user.tenant_id)
    total = query.count()
    items = (
        query.order_by(AuditLog.created_at.desc())
        .offset((pagination.page - 1) * pagination.page_size)
        .limit(pagination.page_size)
        .all()
    )
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "total": total,
            "page": pagination.page,
            "page_size": pagination.page_size,
            "items": [_to_audit_response(log) for log in items],
        },
    }
