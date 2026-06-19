"""Agent 可调用的业务工具封装."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.document import Document
from app.models.user import User
from app.services.audit_service import log_action
from app.services.query_service import QueryService
from app.services.rag_service import RagService, RagUnavailableError
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


def _extract_document_text(document: Document) -> str:
    """从文档解析结果中提取可索引文本."""
    parse_result = document.parse_result or {}
    if "text" in parse_result and isinstance(parse_result["text"], str):
        return parse_result["text"]
    if "markdown" in parse_result and isinstance(parse_result["markdown"], str):
        return parse_result["markdown"]
    if "records" in parse_result and isinstance(parse_result["records"], list):
        lines = []
        for record in parse_result["records"]:
            if isinstance(record, dict):
                lines.append(", ".join(f"{k}: {v}" for k, v in record.items()))
        return "\n".join(lines)
    return ""


def document_qa_tool(
    question: str,
    tenant_id: str,
    document_id: str | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    """基于文档内容的 RAG 问答工具.

    Args:
        question: 用户问题。
        tenant_id: 租户 ID。
        document_id: 指定文档 ID，None 则自动选择该租户最新已完成/复核文档。
        db: 可选的数据库会话，用于测试注入。

    Returns:
        RagService.query 的结果，包含 answer、chunks、document_id。
    """
    session = _get_session(db)
    try:
        if document_id is None:
            doc = (
                session.query(Document)
                .filter(
                    Document.tenant_id == tenant_id,
                    Document.status.in_({"completed", "needs_review"}),
                )
                .order_by(Document.created_at.desc())
                .first()
            )
        else:
            doc = (
                session.query(Document)
                .filter(
                    Document.id == document_id,
                    Document.tenant_id == tenant_id,
                )
                .first()
            )

        if doc is None:
            return {
                "answer": "未找到可用于问答的文档，请先上传并解析文档。",
                "chunks": [],
                "document_id": document_id,
            }

        rag = RagService()
        text = _extract_document_text(doc)
        if not text:
            return {
                "answer": "文档暂无可用文本内容。",
                "chunks": [],
                "document_id": str(doc.id),
            }

        rag.index_document(str(doc.id), text, tenant_id=tenant_id)
        try:
            result = rag.query(question, tenant_id=tenant_id, document_id=str(doc.id))
            log_action(
                db=session,
                action="documents.qa",
                resource=f"document://{doc.id}",
                result="success",
                reason=f"question={question}",
            )
            return result
        except RagUnavailableError as exc:
            log_action(
                db=session,
                action="documents.qa",
                resource=f"document://{doc.id}",
                result="failed",
                reason=f"question={question}, error={exc!s}",
            )
            return {
                "answer": f"文档问答服务暂不可用：{exc!s}",
                "chunks": [],
                "document_id": str(doc.id),
            }
    finally:
        if db is None:
            session.close()
