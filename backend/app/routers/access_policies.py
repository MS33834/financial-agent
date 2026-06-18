"""ABAC 策略管理路由.

仅管理员可创建/修改策略；所有登录用户可查看本租户策略。
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.roles import Role
from app.database import get_db
from app.dependencies import require_abac_permission, require_role
from app.models.access_policy import AccessPolicy
from app.models.user import User
from app.schemas.access_policy import (
    AccessPolicyCreate,
    AccessPolicyResponse,
    AccessPolicyUpdate,
)
from app.schemas.common import DataResponse, PaginationParams

router = APIRouter(prefix="/api/v1/access-policies", tags=["Access Policies"])


def _to_response(policy: AccessPolicy) -> dict[str, Any]:
    return {
        "id": policy.id,
        "tenant_id": policy.tenant_id,
        "name": policy.name,
        "resource_type": policy.resource_type,
        "action": policy.action,
        "effect": policy.effect,
        "priority": policy.priority,
        "conditions": policy.conditions,
        "description": policy.description,
        "is_active": policy.is_active,
    }


@router.get("", response_model=DataResponse[list[AccessPolicyResponse]])
def list_policies(
    params: PaginationParams = Depends(),
    user: User = Depends(require_abac_permission("access_policy", "read")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """列出本租户访问策略."""
    query = db.query(AccessPolicy).filter(AccessPolicy.tenant_id == user.tenant_id)
    total = query.count()
    items = (
        query.order_by(AccessPolicy.priority.asc(), AccessPolicy.created_at.desc())
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
        .all()
    )
    return {
        "code": 0,
        "message": "ok",
        "data": [_to_response(item) for item in items],
        "pagination": {"page": params.page, "page_size": params.page_size, "total": total},
    }


@router.post("", response_model=DataResponse[AccessPolicyResponse], status_code=status.HTTP_201_CREATED)
def create_policy(
    data: AccessPolicyCreate,
    user: User = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """创建访问策略（管理员）."""
    policy = AccessPolicy(
        tenant_id=user.tenant_id,
        name=data.name,
        resource_type=data.resource_type,
        action=data.action,
        effect=data.effect,
        priority=data.priority,
        conditions=data.conditions,
        description=data.description,
        is_active=data.is_active,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return {"code": 0, "message": "ok", "data": _to_response(policy)}


@router.put("/{policy_id}", response_model=DataResponse[AccessPolicyResponse])
def update_policy(
    policy_id: str,
    data: AccessPolicyUpdate,
    user: User = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """更新访问策略（管理员）."""
    policy = (
        db.query(AccessPolicy)
        .filter(AccessPolicy.id == policy_id, AccessPolicy.tenant_id == user.tenant_id)
        .first()
    )
    if policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(policy, key, value)

    db.commit()
    db.refresh(policy)
    return {"code": 0, "message": "ok", "data": _to_response(policy)}


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_policy(
    policy_id: str,
    user: User = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> None:
    """删除访问策略（管理员）."""
    policy = (
        db.query(AccessPolicy)
        .filter(AccessPolicy.id == policy_id, AccessPolicy.tenant_id == user.tenant_id)
        .first()
    )
    if policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
    db.delete(policy)
    db.commit()
