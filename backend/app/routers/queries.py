"""自然语言查询路由."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.user import User
from app.schemas.common import DataResponse
from app.schemas.query import NLQueryRequest, NLQueryResponse
from app.services.query_service import QueryService

router = APIRouter(prefix="/api/v1/queries", tags=["Queries"])


@router.post("/nl2sql", response_model=DataResponse[NLQueryResponse])
def nl2sql_query(
    request: NLQueryRequest,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """自然语言转 SQL 查询并执行."""
    question = request.question.strip()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question is required",
        )

    service = QueryService()
    result = service.nl2sql(question, str(user.tenant_id), db)

    return {
        "code": 0,
        "message": "ok",
        "data": result,
    }
