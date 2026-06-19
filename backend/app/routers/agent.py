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
from app.services.audit_service import log_action

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

    def _truncate_reason(text: str, max_len: int = 200) -> str:
        """截断审计 reason 避免过长."""
        return text if len(text) <= max_len else text[:max_len] + "..."

    tenant_id = str(user.tenant_id)
    log_action(
        db=db,
        action="agent.chat",
        resource=f"agent://{tenant_id}",
        result="started",
        user=user,
        reason=_truncate_reason(f"question={request.question}"),
    )

    result = run_agent(
        question=request.question,
        tenant_id=tenant_id,
        user_id=str(user.id),
        db=db,
    )

    has_error = result.get("error") is not None
    log_action(
        db=db,
        action="agent.chat",
        resource=f"agent://{tenant_id}",
        result="success" if not has_error else "failed",
        user=user,
        reason=_truncate_reason(
            str(result.get("error")) if has_error else f"intent={result.get('intent')}"
        ),
    )

    return {
        "code": 0,
        "message": "ok",
        "data": result,
    }
