"""Agent 可调用的业务工具封装."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.user import User
from app.services.query_service import QueryService
from app.services.report_service import create_report_task
from app.tasks.document_tasks import parse_document_task


def _get_session(db: Session | None) -> Session:
    """获取数据库会话，优先使用传入的会话."""
    if db is not None:
        return db
    return SessionLocal()


def nl2sql_tool(
    question: str,
    tenant_id: str,
    db: Session | None = None,
    user: User | None = None,
) -> dict[str, Any]:
    """自然语言转 SQL 查询工具.

    Args:
        question: 用户问题。
        tenant_id: 租户 ID。
        db: 可选的数据库会话，用于测试注入。
        user: 当前用户，用于审计；可选。

    Returns:
        QueryService.nl2sql 的返回结果。
    """
    session = _get_session(db)
    try:
        return QueryService().nl2sql(question, tenant_id, session, user=user)
    finally:
        if db is None:
            session.close()


def create_report_tool(
    title: str,
    report_type: str,
    parameters: dict[str, Any],
    tenant_id: str,
    user_id: str,
    db: Session | None = None,
) -> dict[str, Any]:
    """创建财务报告任务工具.

    Args:
        title: 报告标题。
        report_type: 报告类型。
        parameters: 报告参数。
        tenant_id: 租户 ID。
        user_id: 用户 ID。
        db: 可选的数据库会话，用于测试注入。

    Returns:
        包含 report_id、status、title 的字典。
    """
    from app.models.user import User
    from app.schemas.report import ReportCreate

    session = _get_session(db)
    try:
        user = session.query(User).filter(User.id == user_id, User.tenant_id == tenant_id).first()
        if user is None:
            return {"error": "User not found"}

        data = ReportCreate(
            title=title,
            report_type=report_type,  # type: ignore[arg-type]
            parameters=parameters,
        )
        report = create_report_task(db=session, data=data, user=user)
        return {
            "report_id": report.id,
            "status": report.status,
            "title": report.title,
        }
    finally:
        if db is None:
            session.close()


def parse_document_tool(document_id: str) -> dict[str, Any]:
    """触发文档解析任务工具.

    Args:
        document_id: 文档 ID。

    Returns:
        包含 document_id 与 task_id 的字典。
    """
    task = parse_document_task.delay(document_id)
    return {"document_id": document_id, "task_id": task.id}
