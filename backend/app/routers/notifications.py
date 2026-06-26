"""通知管理路由.

提供用户站内信列表查询与已读标记接口。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import DataResponse
from notification import get_notification_service

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


@router.get("", response_model=DataResponse)
def list_notifications(
    unread_only: bool = Query(default=False, description="仅返回未读"),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """查询当前用户的站内信列表."""
    settings = get_settings()
    service = get_notification_service(db, settings)
    items = service.list_user_notifications(user.id, unread_only=unread_only, limit=limit)
    return {"code": 0, "message": "ok", "data": items}


@router.post("/{notification_id}/read", response_model=DataResponse)
def mark_read(
    notification_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """标记站内信为已读."""
    settings = get_settings()
    service = get_notification_service(db, settings)
    success = service.mark_as_read(notification_id, user.id)
    return {"code": 0 if success else 404, "message": "ok" if success else "通知不存在", "data": success}
