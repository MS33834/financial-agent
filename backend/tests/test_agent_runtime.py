"""LangGraph Agent 运行时测试."""

from __future__ import annotations

from unittest import mock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.financial_report import FinancialReport
from app.models.tenant import Tenant


def _seed_report(db_session: Session, tenant: Tenant) -> FinancialReport:
    """插入示例财报数据."""
    report = FinancialReport(
        tenant_id=tenant.id,
        year=2025,
        period="Q2",
        net_profit=1_000_000.0,
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)
    return report


def test_agent_nl2sql_intent(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_tenant: Tenant,
) -> None:
    """Agent 应识别 NL2SQL 意图并返回答案."""
    _seed_report(db_session, test_tenant)

    payload = {"question": "2025 年 Q2 净利润是多少"}
    response = client.post("/api/v1/agent/chat", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"] == "nl2sql"
    assert data["answer"] is not None
    assert "1000000.0" in data["answer"] or "1000000" in data["answer"]


def test_agent_create_report_intent(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """Agent 应识别创建报告意图."""
    payload = {"question": "生成 2025 年利润表"}
    response = client.post("/api/v1/agent/chat", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"] == "create_report"
    assert data["tool_result"]["report_id"] is not None


def test_agent_unknown_intent(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """Agent 对未知意图返回错误提示."""
    payload = {"question": "今天天气怎么样"}
    response = client.post("/api/v1/agent/chat", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"] == "unknown"
    assert "无法识别" in data["answer"]


def _seed_document(db_session: Session, tenant: Tenant) -> Document:
    """插入示例已解析文档."""
    document = Document(
        tenant_id=tenant.id,
        filename="demo_report.pdf",
        storage_key="demo/report.pdf",
        status="completed",
        parse_result={"text": "公司 2025 年 Q2 营收增长 20%，净利润提升 15%。"},
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


def test_agent_document_qa_intent(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_tenant: Tenant,
) -> None:
    """Agent 应识别文档问答意图并返回答案."""
    _seed_document(db_session, test_tenant)

    with mock.patch("app.agent_runtime.tools.RagService") as mock_rag_service:
        mock_rag_service.return_value.query.return_value = {
            "answer": "根据文档内容，2025 年 Q2 营收增长 20%。",
            "chunks": ["公司 2025 年 Q2 营收增长 20%"],
            "document_id": "doc-id",
        }
        payload = {"question": "这份文档讲了什么"}
        response = client.post("/api/v1/agent/chat", json=payload, headers=auth_headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"] == "document_qa"
    assert "营收增长" in data["answer"]


def test_agent_chat_unauthorized(client: TestClient) -> None:
    """未认证访问 Agent 接口应被拒绝."""
    response = client.post("/api/v1/agent/chat", json={"question": "test"})
    assert response.status_code == 401
