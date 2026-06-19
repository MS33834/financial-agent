"""LangGraph Agent 路由."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent_runtime.graph import run_agent
from app.database import get_db
from app.dependencies import get_current_user_or_api_key
from app.models.user import User
from app.schemas.common import DataResponse

router = APIRouter(prefix="/api/v1/agent", tags=["Agent"])


class AgentChatRequest(BaseModel):
    """Agent 对话请求."""

    question: str = Field(description="用户自然语言问题", min_length=1)


@router.post("/chat", response_model=DataResponse[dict[str, Any]])
def agent_chat(
    request: AgentChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_api_key(scope="queries:nl2sql")),
) -> dict[str, Any]:
    """直接调用 LangGraph Agent 处理自然语言请求.

    Agent 会根据意图自动选择 NL2SQL、报告创建或文档解析工具。
    """
    result = run_agent(
        question=request.question,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        db=db,
    )
    return {
        "code": 0,
        "message": "ok",
        "data": result,
    }
