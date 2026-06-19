"""API Key 管理路由."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.roles import Role
from app.database import get_db
from app.dependencies import get_pagination, require_role
from app.models.user import User
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreateResponse, ApiKeyListResponse
from app.schemas.common import DataResponse, PaginationParams
from app.services.api_key_service import (
    create_api_key,
    delete_api_key,
    list_api_keys,
    revoke_api_key,
)

router = APIRouter(prefix="/api/v1/api-keys", tags=["API Keys"])


@router.post(
    "",
    response_model=DataResponse[ApiKeyCreateResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_key(
    data: ApiKeyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.AUDITOR)),
) -> dict[str, Any]:
    """为当前租户创建 API Key，明文 key 仅返回一次."""
    api_key, plain_key = create_api_key(db=db, user=user, data=data)
    return {
        "code": 0,
        "message": "ok",
        "data": {
            **api_key.to_dict(),
            "key": plain_key,
        },
    }


@router.get("", response_model=DataResponse[ApiKeyListResponse])
def list_keys(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.AUDITOR)),
    pagination: PaginationParams = Depends(get_pagination),
) -> dict[str, Any]:
    """查询当前租户下的 API Key 列表."""
    result = list_api_keys(db=db, tenant_id=user.tenant_id, pagination=pagination)
    return {
        "code": 0,
        "message": "ok",
        "data": result,
    }


@router.post("/{key_id}/revoke", response_model=DataResponse[dict[str, Any]])
def revoke_key(
    key_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.AUDITOR)),
) -> dict[str, Any]:
    """吊销指定 API Key."""
    if not revoke_api_key(db=db, key_id=key_id, tenant_id=user.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key not found",
        )
    return {
        "code": 0,
        "message": "ok",
        "data": {"id": key_id, "is_active": "N"},
    }


@router.delete("/{key_id}", response_model=DataResponse[dict[str, Any]])
def delete_key(
    key_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN, Role.AUDITOR)),
) -> dict[str, Any]:
    """删除指定 API Key."""
    if not delete_api_key(db=db, key_id=key_id, tenant_id=user.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key not found",
        )
    return {
        "code": 0,
        "message": "ok",
        "data": {"id": key_id, "deleted": True},
    }
