"""API 层端到端集成测试.

覆盖三条核心业务链路的完整流程：
1. 文档上传 -> 解析 -> 查询
2. 报告创建 -> 生成 -> 审批
3. Agent 问答

这些测试使用真实数据库连接（SessionLocal），与单元测试的事务回滚会话不同，
因此以 ``@pytest.mark.integration`` 标记，默认在普通测试运行时跳过，
仅当显式 ``pytest -m integration`` 时执行。
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from io import BytesIO
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.main import app
from app.models.financial_report import FinancialReport
from app.models.tenant import Tenant
from app.models.user import User
from app.security import get_password_hash


class FakeStorageClient:
    """测试用对象存储客户端，记录上传内容便于断言."""

    def __init__(self) -> None:
        self.stored: dict[str, bytes] = {}
        self.uploaded: list[dict[str, Any]] = []

    def upload_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        self.stored[key] = data
        self.uploaded.append(
            {"key": key, "data": data, "content_type": content_type, "metadata": metadata}
        )
        return f"http://fake-minio/financial-agent/{key}"

    def download_bytes(self, key: str) -> bytes:
        if key not in self.stored:
            raise RuntimeError(f"Object {key} not found")
        return self.stored[key]


@pytest.fixture
def e2e_db() -> Generator[Session, None, None]:
    """使用真实 SessionLocal 的会话（已提交数据对异步任务可见）."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _create_user(
    db: Session,
    tenant: Tenant,
    username: str,
    role: str = "admin",
) -> User:
    """创建并提交测试用户."""
    user = User(
        tenant_id=tenant.id,
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash("testpass"),
        role=role,
        is_active="Y",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _seed_financial_data(db: Session, tenant: Tenant) -> FinancialReport:
    """为集成测试准备已提交的财报数据."""
    report = FinancialReport(
        tenant_id=tenant.id,
        year=2025,
        period="Q2",
        revenue=10_000_000,
        operating_cost=6_000_000,
        operating_profit=2_000_000,
        net_profit=1_500_000,
        total_assets=50_000_000,
        total_liabilities=20_000_000,
        owner_equity=30_000_000,
        cash_flow_operating=3_000_000,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def _make_excel_content(rows: list[dict[str, Any]]) -> bytes:
    """构造内存 Excel 文件字节."""
    wb = Workbook()
    ws = wb.active
    if rows:
        headers = list(rows[0].keys())
        ws.append(headers)
        for row in rows:
            ws.append([row.get(h) for h in headers])
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _login(client: TestClient, username: str, password: str = "testpass") -> str:
    """登录并返回 access token."""
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return cast(str, resp.json()["data"]["access_token"])


@pytest.mark.integration
def test_document_upload_parse_query_flow(
    e2e_db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """文档上传 -> 解析 -> 查询的完整流程."""
    tenant = Tenant(name="IT Doc Tenant", code=f"it-doc-{uuid.uuid4().hex[:8]}")
    e2e_db.add(tenant)
    e2e_db.commit()
    e2e_db.refresh(tenant)
    admin = _create_user(e2e_db, tenant, f"it-doc-admin-{uuid.uuid4().hex[:8]}")

    fake_storage = FakeStorageClient()
    monkeypatch.setattr("app.routers.documents.get_storage_client", lambda: fake_storage)
    monkeypatch.setattr("app.tasks.document_tasks.get_storage_client", lambda: fake_storage)

    valid_rows = [
        {
            "year": 2025,
            "period": "Q2",
            "revenue": 10_000_000,
            "operating_cost": 6_000_000,
            "operating_profit": 2_000_000,
            "net_profit": 1_500_000,
            "total_assets": 50_000_000,
            "total_liabilities": 20_000_000,
            "owner_equity": 30_000_000,
            "cash_flow_operating": 3_000_000,
        }
    ]
    excel_content = _make_excel_content(valid_rows)

    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {_login(client, admin.username)}"}

        # 1. 上传 Excel 并触发解析
        upload_resp = client.post(
            "/api/v1/documents/upload",
            files={
                "file": (
                    "profit_2025_q2.xlsx",
                    BytesIO(excel_content),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            headers=headers,
        )
        assert upload_resp.status_code == 201, upload_resp.text
        doc_id = upload_resp.json()["data"]["id"]

        # 2. 断言解析完成
        doc_resp = client.get(f"/api/v1/documents/{doc_id}", headers=headers)
        assert doc_resp.status_code == 200
        assert doc_resp.json()["data"]["status"] == "success"

        financial_report = (
            e2e_db.query(FinancialReport)
            .filter(
                FinancialReport.tenant_id == tenant.id,
                FinancialReport.year == 2025,
                FinancialReport.period == "Q2",
            )
            .first()
        )
        assert financial_report is not None
        assert financial_report.revenue == 10_000_000

        # 3. 自然语言查询解析后的数据
        query_resp = client.post(
            "/api/v1/queries/nl2sql",
            headers=headers,
            json={"question": "2025 Q2 营业收入是多少？"},
        )
        assert query_resp.status_code == 200
        query_data = query_resp.json()["data"]
        assert "sql" in query_data
        assert any(row.get("revenue") == 10_000_000 for row in query_data["data"])


@pytest.mark.integration
def test_report_create_generate_approve_flow(e2e_db: Session) -> None:
    """报告创建 -> 生成 -> 审批的完整流程."""
    tenant = Tenant(name="IT Report Tenant", code=f"it-rpt-{uuid.uuid4().hex[:8]}")
    e2e_db.add(tenant)
    e2e_db.commit()
    e2e_db.refresh(tenant)
    admin = _create_user(e2e_db, tenant, f"it-rpt-admin-{uuid.uuid4().hex[:8]}")
    _seed_financial_data(e2e_db, tenant)

    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {_login(client, admin.username)}"}

        # 1. 创建报告生成任务
        create_resp = client.post(
            "/api/v1/reports",
            headers=headers,
            json={
                "title": "2025 Q2 利润表",
                "report_type": "profit",
                "parameters": {"year": 2025, "period": "Q2"},
            },
        )
        assert create_resp.status_code == 201, create_resp.text
        report_id = create_resp.json()["data"]["id"]

        # 2. 获取报告并验证已生成成功
        get_resp = client.get(f"/api/v1/reports/{report_id}", headers=headers)
        assert get_resp.status_code == 200
        report_data = get_resp.json()["data"]
        assert report_data["status"] in ("reviewing", "success")
        assert report_data["content"]["summary"]

        # 3. 审批报告
        approve_resp = client.post(
            f"/api/v1/approvals/{report_id}/action",
            headers=headers,
            json={"action": "approve", "comment": "数据准确，同意发布"},
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["data"]["action"] == "approve"

        # 4. 验证报告状态已变为 approved
        approved_resp = client.get(f"/api/v1/reports/{report_id}", headers=headers)
        assert approved_resp.status_code == 200
        assert approved_resp.json()["data"]["status"] == "approved"


@pytest.mark.integration
def test_agent_qa_flow(e2e_db: Session) -> None:
    """Agent 问答流程：识别 NL2SQL 意图并返回答案."""
    tenant = Tenant(name="IT Agent Tenant", code=f"it-agent-{uuid.uuid4().hex[:8]}")
    e2e_db.add(tenant)
    e2e_db.commit()
    e2e_db.refresh(tenant)
    admin = _create_user(e2e_db, tenant, f"it-agent-admin-{uuid.uuid4().hex[:8]}")

    report = FinancialReport(
        tenant_id=tenant.id,
        year=2025,
        period="Q2",
        revenue=10_000_000,
        net_profit=1_500_000,
    )
    e2e_db.add(report)
    e2e_db.commit()

    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {_login(client, admin.username)}"}

        resp = client.post(
            "/api/v1/agent/chat",
            headers=headers,
            json={"question": "2025 年 Q2 净利润是多少"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["intent"] == "nl2sql"
        assert data["answer"] is not None
        assert "1500000" in str(data["answer"])
