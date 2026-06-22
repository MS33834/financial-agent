"""仪表盘路由."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.user import User
from app.schemas.common import DataResponse
from app.services.dashboard_service import get_dashboard_summary, get_user_greeting

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DataResponse[dict[str, Any]])
def dashboard_summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """获取仪表盘汇总数据."""
    summary = get_dashboard_summary(db=db, tenant_id=user.tenant_id)
    summary["greeting"] = get_user_greeting(user=user)
    return {"code": 0, "message": "ok", "data": summary}
