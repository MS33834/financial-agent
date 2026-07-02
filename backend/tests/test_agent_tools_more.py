"""Agent 工具函数（app.agent_runtime.tools）补全测试.

覆盖：
- nl2sql_tool: 传入 db session 注入、闭包关闭
- create_report_tool: User not found 兜底
- document_qa_tool: 无文档、文档无文本、RAG 索引存在/未索引
- _extract_document_text: text / markdown / records / 空 / 字段类型不符
"""

from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.agent_runtime.tools import (
    _extract_document_text,
    create_report_tool,
    document_qa_tool,
    nl2sql_tool,
    parse_document_tool,
)
from app.models.document import Document
from app.models.tenant import Tenant
from app.models.user import User
from app.security import get_password_hash


def _user(db: Session, tenant: Tenant) -> User:
    u = User(
        tenant_id=tenant.id,
        username="tool-user",
        hashed_password=get_password_hash("initpass1"),
        role="admin",
        is_active="Y",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


# ------------------------------------------------------------------
# _extract_document_text
# ------------------------------------------------------------------


def test_extract_document_text_text_field() -> None:
    """parse_result.text 字段应被返回."""
    doc = MagicMock()
    doc.parse_result = {"text": "hello world"}
    assert _extract_document_text(doc) == "hello world"


def test_extract_document_text_markdown_field() -> None:
    """parse_result.markdown 字段应被返回（text 优先）. 若 text 缺则取 markdown."""
    doc = MagicMock()
    doc.parse_result = {"markdown": "# title\nbody"}
    # 实际：text 缺失但 markdown 存在，代码应仍能取到 markdown
    assert _extract_document_text(doc) == "# title\nbody"


def test_extract_document_text_records_field() -> None:
    """parse_result.records 列表应序列化为 k: v 形式."""
    doc = MagicMock()
    doc.parse_result = {"records": [{"a": 1, "b": "x"}, {"c": True}]}
    result = _extract_document_text(doc)
    assert "a: 1" in result
    assert "b: x" in result
    assert "c: True" in result


def test_extract_document_text_empty() -> None:
    """空 parse_result 应返回空字符串."""
    doc = MagicMock()
    doc.parse_result = {}
    assert _extract_document_text(doc) == ""


def test_extract_document_text_none() -> None:
    """None parse_result 应安全返回空字符串."""
    doc = MagicMock()
    doc.parse_result = None
    assert _extract_document_text(doc) == ""


def test_extract_document_text_wrong_type_text() -> None:
    """text 字段类型不符时不应抛异常（应继续尝试 markdown/records）."""
    doc = MagicMock()
    doc.parse_result = {"text": 123, "markdown": "fallback"}
    assert _extract_document_text(doc) == "fallback"


# ------------------------------------------------------------------
# nl2sql_tool
# ------------------------------------------------------------------


def test_nl2sql_tool_uses_injected_db() -> None:
    """传入 db 时应复用，不创建新 session."""
    fake_db = MagicMock(spec=Session)
    with patch("app.agent_runtime.tools.QueryService") as fake_qs:
        fake_qs.return_value.nl2sql.return_value = {"sql": "SELECT 1"}
        result = nl2sql_tool(
            "本月营收", tenant_id="t1", db=fake_db
        )
    assert result == {"sql": "SELECT 1"}
    fake_qs.return_value.nl2sql.assert_called_once()


def test_nl2sql_tool_creates_session_when_none() -> None:
    """未传入 db 时应创建并关闭 SessionLocal."""
    with patch("app.agent_runtime.tools.QueryService") as fake_qs, \
         patch("app.agent_runtime.tools.SessionLocal") as fake_factory:
        session_instance = MagicMock()
        fake_factory.return_value = session_instance
        fake_qs.return_value.nl2sql.return_value = {"sql": "SELECT 2"}
        result = nl2sql_tool("test", tenant_id="t1")
    assert result == {"sql": "SELECT 2"}
    session_instance.close.assert_called_once()


# ------------------------------------------------------------------
# create_report_tool
# ------------------------------------------------------------------


def test_create_report_tool_user_not_found(
    db_session: Session, test_tenant: Tenant
) -> None:
    """用户不存在时应返回 error 字段而不抛异常."""
    result = create_report_tool(
        title="Q1 report",
        report_type="monthly_revenue",
        parameters={"month": "2026-01"},
        tenant_id=test_tenant.id,
        user_id="ghost",
        db=db_session,
    )
    assert "error" in result
    assert result["error"] == "User not found"


def test_create_report_tool_success(
    db_session: Session, test_tenant: Tenant
) -> None:
    """正常路径应返回 report_id/status/title."""
    user = _user(db_session, test_tenant)
    result = create_report_tool(
        title="Q1 report",
        report_type="profit",
        parameters={"month": "2026-01"},
        tenant_id=test_tenant.id,
        user_id=user.id,
        db=db_session,
    )
    assert "report_id" in result
    assert result["title"] == "Q1 report"


def test_create_report_tool_user_not_found_uses_invalid_type(
    db_session: Session, test_tenant: Tenant
) -> None:
    """user 找不到时不应走到 ReportCreate 校验（早返回）."""
    result = create_report_tool(
        title="x",
        report_type="profit",
        parameters={},
        tenant_id=test_tenant.id,
        user_id="ghost",
        db=db_session,
    )
    assert result.get("error") == "User not found"


# ------------------------------------------------------------------
# parse_document_tool
# ------------------------------------------------------------------


def test_parse_document_tool_triggers_task() -> None:
    """parse_document_tool 应触发 celery 任务并返回 task_id."""
    with patch("app.agent_runtime.tools.parse_document_task") as fake_task:
        fake_task.delay.return_value = MagicMock(id="task-123")
        result = parse_document_tool("doc-xyz")
    assert result == {"document_id": "doc-xyz", "task_id": "task-123"}
    fake_task.delay.assert_called_once_with("doc-xyz")


# ------------------------------------------------------------------
# document_qa_tool
# ------------------------------------------------------------------


def test_document_qa_tool_no_document_found(
    db_session: Session, test_tenant: Tenant
) -> None:
    """找不到文档时应返回提示."""
    result = document_qa_tool(
        "本月营收", tenant_id=test_tenant.id, db=db_session
    )
    assert "未找到" in result["answer"]
    assert result["chunks"] == []


def test_document_qa_tool_document_has_no_text(
    db_session: Session, test_tenant: Tenant
) -> None:
    """文档无 parse_result 时应返回提示."""
    doc = Document(
        tenant_id=test_tenant.id,
        filename="x.pdf",
        storage_key="x",
        status="success",
        parse_result={},
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    result = document_qa_tool(
        "test", tenant_id=test_tenant.id, document_id=doc.id, db=db_session
    )
    assert "无可用文本" in result["answer"]


def test_document_qa_tool_no_text_in_db_falls_back_to_empty(
    db_session: Session, test_tenant: Tenant
) -> None:
    """无 doc 时走 fallback 分支（不抛异常）."""
    result = document_qa_tool(
        "test", tenant_id=test_tenant.id, document_id="ghost", db=db_session
    )
    assert "answer" in result


def test_document_qa_tool_uses_in_memory_index(
    db_session: Session, test_tenant: Tenant
) -> None:
    """文档已有内存索引时应直接查询."""
    from app.services.rag_service import RagService

    # 在 RagService 单例中预置索引
    rag = RagService()
    doc = Document(
        tenant_id=test_tenant.id,
        filename="x.pdf",
        storage_key="x",
        status="success",
        parse_result={"text": "hello world"},
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    rag._index[(test_tenant.id, doc.id)] = [
        {"chunk": "hello world", "embedding": [0.0, 1.0]},
    ]

    with patch("app.agent_runtime.tools.RagService", return_value=rag), \
         patch("app.services.rag_service.embed", return_value=[0.0, 1.0]):
        result = document_qa_tool(
            "test",
            tenant_id=test_tenant.id,
            document_id=doc.id,
            db=db_session,
        )
    assert "hello world" in result["answer"]
    assert result["document_id"] == doc.id
