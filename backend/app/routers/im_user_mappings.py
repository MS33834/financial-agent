"""IM 用户映射管理路由.

提供管理员维护 IM 平台用户 ID 与系统用户映射的 CRUD 接口。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_pagination, require_role
from app.models.im_user_mapping import IMUserMapping
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationParams

router = APIRouter(prefix="/api/v1/im-user-mappings", tags=["IM User Mappings"])


@router.get("", response_model=PaginatedResponse[dict[str, Any]])
def list_im_user_mappings(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "auditor")),
    pagination: PaginationParams = Depends(get_pagination),
    platform: str | None = Query(default=None, description="按平台筛选"),
) -> dict[str, Any]:
    """查询当前租户下的 IM 用户映射列表."""
    query = db.query(IMUserMapping).filter(IMUserMapping.tenant_id == user.tenant_id)
    if platform:
        query = query.filter(IMUserMapping.platform == platform)

    total = query.count()
    items = (
        query.order_by(IMUserMapping.created_at.desc())
        .offset((pagination.page - 1) * pagination.page_size)
        .limit(pagination.page_size)
        .all()
    )
    return {
        "data": {
            "items": [
                {
                    "id": item.id,
                    "user_id": item.user_id,
                    "platform": item.platform,
                    "im_user_id": item.im_user_id,
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                    "updated_at": item.updated_at.isoformat() if item.updated_at else None,
                }
                for item in items
            ],
            "total": total,
            "page": pagination.page,
            "page_size": pagination.page_size,
        }
    }


@router.post("", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
def create_im_user_mapping(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "auditor")),
) -> dict[str, Any]:
    """创建 IM 用户映射."""
    target_user_id = payload.get("user_id")
    platform = payload.get("platform")
    im_user_id = payload.get("im_user_id")

    if not target_user_id or not platform or not im_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id、platform、im_user_id 均为必填项",
        )

    target_user: User | None = db.query(User).filter(
        User.id == target_user_id,
        User.tenant_id == user.tenant_id,
        User.is_active == "Y",
    ).first()
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到指定用户",
        )

    existing = (
        db.query(IMUserMapping)
        .filter(
            IMUserMapping.tenant_id == user.tenant_id,
            IMUserMapping.platform == platform,
            IMUserMapping.im_user_id == im_user_id,
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该 IM 用户在此平台下已存在映射",
        )

    mapping = IMUserMapping(
        tenant_id=user.tenant_id,
        user_id=target_user_id,
        platform=platform,
        im_user_id=im_user_id,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return {
        "id": mapping.id,
        "user_id": mapping.user_id,
        "platform": mapping.platform,
        "im_user_id": mapping.im_user_id,
        "created_at": mapping.created_at.isoformat() if mapping.created_at else None,
        "updated_at": mapping.updated_at.isoformat() if mapping.updated_at else None,
    }


@router.delete("/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_im_user_mapping(
    mapping_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "auditor")),
) -> None:
    """删除指定 IM 用户映射."""
    mapping: IMUserMapping | None = (
        db.query(IMUserMapping)
        .filter(
            IMUserMapping.id == mapping_id,
            IMUserMapping.tenant_id == user.tenant_id,
        )
        .first()
    )
    if mapping is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到指定映射",
        )
    db.delete(mapping)
    db.commit()
