"""错误自省路由."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_pagination, require_role
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.services.reflection_service import ReflectionService

router = APIRouter(prefix="/api/v1/reflections", tags=["Reflections"])


class ResolveReflectionRequest(BaseModel):
    """解决自省日志请求."""

    resolution: str = Field(..., min_length=1, max_length=2000, description="解决方案")


def _to_reflection_response(reflection: Any) -> dict[str, Any]:
    """将 ORM 对象转为响应字典."""
    return {
        "id": reflection.id,
        "created_at": reflection.created_at.isoformat() if reflection.created_at else None,
        "tenant_id": reflection.tenant_id,
        "task_name": reflection.task_name,
        "task_id": reflection.task_id,
        "resource_type": reflection.resource_type,
        "resource_id": reflection.resource_id,
        "exception_type": reflection.exception_type,
        "exception_message": reflection.exception_message,
        "stack_trace": reflection.stack_trace,
        "error_category": reflection.error_category,
        "root_cause": reflection.root_cause,
        "suggested_fix": reflection.suggested_fix,
        "retried": reflection.retried,
        "resolved": reflection.resolved,
        "resolution": reflection.resolution,
    }


@router.get("", response_model=PaginatedResponse[dict[str, Any]])
def list_reflections(
    category: str | None = None,
    resolved: bool | None = None,
    resource_type: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "auditor")),
    pagination: PaginationParams = Depends(get_pagination),
) -> dict[str, Any]:
    """查询错误自省日志（仅管理员/审计员）."""
    service = ReflectionService(db)
    items, total = service.list_reflections(
        tenant_id=user.tenant_id,
        category=category,
        resolved=resolved,
        resource_type=resource_type,
        pagination=pagination,
    )
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "total": total,
            "page": pagination.page,
            "page_size": pagination.page_size,
            "items": [_to_reflection_response(item) for item in items],
        },
    }


@router.get("/{reflection_id}", response_model=dict[str, Any])
def get_reflection(
    reflection_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "auditor")),
) -> dict[str, Any]:
    """获取单条错误自省日志."""
    service = ReflectionService(db)
    reflection = service.get_reflection(reflection_id, tenant_id=user.tenant_id)
    if reflection is None:
        raise HTTPException(status_code=404, detail="自省日志不存在")
    return {
        "code": 0,
        "message": "ok",
        "data": _to_reflection_response(reflection),
    }


@router.post("/{reflection_id}/resolve", response_model=dict[str, Any])
def resolve_reflection(
    reflection_id: str,
    body: ResolveReflectionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "auditor")),
) -> dict[str, Any]:
    """标记错误自省日志为已解决."""
    service = ReflectionService(db)
    reflection = service.resolve(reflection_id, body.resolution, tenant_id=user.tenant_id)
    if reflection is None:
        raise HTTPException(status_code=404, detail="自省日志不存在")
    return {
        "code": 0,
        "message": "ok",
        "data": _to_reflection_response(reflection),
    }
