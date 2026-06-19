"""端到端用户旅程测试.

模拟一个典型工作流：
管理员登录 → 上传 Excel 并解析 → 低置信度人工复核 → NL2SQL 查询
→ 创建报告 → 导出 PDF/Excel → 审批报告 → 查看审计日志。
同时验证权限边界：finance_manager 可上传，viewer 不能上传/导出。

注意：异步任务使用独立的 SessionLocal，为避免事务隔离导致任务看不到
未提交数据，本测试使用真实的已提交数据库会话进行准备与断言。
"""

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
from app.models.document import Document
from app.models.financial_report import FinancialReport
from app.models.report import Report
from app.models.tenant import Tenant
from app.models.user import User
from app.security import get_password_hash
from app.tasks.report_tasks import generate_report_task


class FakeStorageClient:
    """测试用对象存储客户端."""

    def __init__(self, stored: dict[str, bytes] | None = None) -> None:
        """初始化."""
        self.stored = stored or {}
        self.uploaded: list[dict[str, Any]] = []

    def upload_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """模拟上传."""
        self.stored[key] = data
        self.uploaded.append(
            {"key": key, "data": data, "content_type": content_type, "metadata": metadata}
        )
        return f"http://fake-minio/financial-agent/{key}"

    def download_bytes(self, key: str) -> bytes:
        """模拟下载."""
        if key not in self.stored:
            raise RuntimeError(f"Object {key} not found")
        return self.stored[key]


@pytest.fixture
def e2e_db() -> Generator[Session, None, None]:
    """使用真实 SessionLocal 并已提交的会话."""
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


def _seed_financial_data(db: Session, tenant: Tenant) -> None:
    """为端到端测试准备财务数据."""
    report = FinancialReport(
        tenant_id=tenant.id,
        year=2025,
        period="Q2",
        revenue=1_000_000,
        operating_cost=600_000,
        operating_profit=200_000,
        net_profit=150_000,
        total_assets=5_000_000,
        total_liabilities=2_000_000,
        owner_equity=3_000_000,
        cash_flow_operating=300_000,
    )
    db.add(report)
    db.commit()


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
    assert resp.status_code == 200
    return cast(str, resp.json()["data"]["access_token"])


def test_admin_journey(e2e_db: Session) -> None:
    """管理员完整工作流."""
    tenant = Tenant(name="E2E Tenant", code=f"e2e-{uuid.uuid4().hex[:8]}")
    e2e_db.add(tenant)
    e2e_db.commit()
    e2e_db.refresh(tenant)

    user = _create_user(e2e_db, tenant, f"admin-{uuid.uuid4().hex[:8]}")
    _seed_financial_data(e2e_db, tenant)

    with TestClient(app) as client:
        # 1. 登录
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username": user.username, "password": "testpass"},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. NL2SQL 查询
        query_resp = client.post(
            "/api/v1/queries/nl2sql",
            headers=headers,
            json={"question": "2025 Q2 营业收入是多少？"},
        )
        assert query_resp.status_code == 200
        query_data = query_resp.json()["data"]
        assert query_data["question"]
        assert "sql" in query_data

        # 3. 创建报告
        create_resp = client.post(
            "/api/v1/reports",
            headers=headers,
            json={
                "title": "2025 Q2 利润表",
                "report_type": "profit",
                "parameters": {"year": 2025, "period": "Q2"},
            },
        )
        assert create_resp.status_code == 201
        report_id = create_resp.json()["data"]["id"]

        # 4. 获取报告并验证已生成成功
        get_resp = client.get(f"/api/v1/reports/{report_id}", headers=headers)
        assert get_resp.status_code == 200
        report = get_resp.json()["data"]
        assert report["status"] in ("reviewing", "success")
        assert report["content"]["summary"]

        # 5. 审批报告
        approve_resp = client.post(
            f"/api/v1/approvals/{report_id}/action",
            headers=headers,
            json={"action": "approve", "comment": "数据准确，同意发布"},
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["data"]["action"] == "approve"

        # 验证报告状态已变为 approved
        get_approved_resp = client.get(f"/api/v1/reports/{report_id}", headers=headers)
        assert get_approved_resp.status_code == 200
        assert get_approved_resp.json()["data"]["status"] == "approved"

        # 6. 查看审计日志
        audit_resp = client.get("/api/v1/audit/logs", headers=headers)
        assert audit_resp.status_code == 200
        logs = audit_resp.json()["data"]["items"]
        actions = {log["action"] for log in logs}
        assert "report.create" in actions
        assert "report.generate.success" in actions
        assert "report.approval.approve" in actions


def test_viewer_cannot_approve(e2e_db: Session) -> None:
    """viewer 角色不能审批报告."""
    tenant = Tenant(name="E2E Viewer Tenant", code=f"e2e-viewer-{uuid.uuid4().hex[:8]}")
    e2e_db.add(tenant)
    e2e_db.commit()
    e2e_db.refresh(tenant)

    admin = _create_user(e2e_db, tenant, f"admin-v-{uuid.uuid4().hex[:8]}")
    viewer = _create_user(e2e_db, tenant, f"viewer-{uuid.uuid4().hex[:8]}", role="viewer")
    _seed_financial_data(e2e_db, tenant)

    with TestClient(app) as client:
        admin_token = client.post(
            "/api/v1/auth/login",
            json={"username": admin.username, "password": "testpass"},
        ).json()["data"]["access_token"]
        viewer_token = client.post(
            "/api/v1/auth/login",
            json={"username": viewer.username, "password": "testpass"},
        ).json()["data"]["access_token"]

        create_resp = client.post(
            "/api/v1/reports",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title": "viewer test report",
                "report_type": "profit",
                "parameters": {"year": 2025, "period": "Q2"},
            },
        )
        report_id = create_resp.json()["data"]["id"]

        approve_resp = client.post(
            f"/api/v1/approvals/{report_id}/action",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={"action": "approve", "comment": "should fail"},
        )
        assert approve_resp.status_code == 403


def test_viewer_cannot_access_audit_logs(e2e_db: Session) -> None:
    """viewer 角色不能查看审计日志."""
    tenant = Tenant(name="E2E Audit Tenant", code=f"e2e-audit-{uuid.uuid4().hex[:8]}")
    e2e_db.add(tenant)
    e2e_db.commit()
    e2e_db.refresh(tenant)

    viewer = _create_user(e2e_db, tenant, f"viewer-a-{uuid.uuid4().hex[:8]}", role="viewer")

    with TestClient(app) as client:
        viewer_token = client.post(
            "/api/v1/auth/login",
            json={"username": viewer.username, "password": "testpass"},
        ).json()["data"]["access_token"]

        resp = client.get(
            "/api/v1/audit/logs",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert resp.status_code == 403


def test_full_mvp_journey(
    e2e_db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """管理员完整 MVP 旅程：上传-解析-查询-报告-导出-审批-审计."""
    tenant = Tenant(name="MVP Tenant", code=f"e2e-mvp-{uuid.uuid4().hex[:8]}")
    e2e_db.add(tenant)
    e2e_db.commit()
    e2e_db.refresh(tenant)

    admin = _create_user(e2e_db, tenant, f"admin-mvp-{uuid.uuid4().hex[:8]}")

    fake_storage = FakeStorageClient()
    monkeypatch.setattr("app.routers.documents.get_storage_client", lambda: fake_storage)
    monkeypatch.setattr("app.tasks.document_tasks.get_storage_client", lambda: fake_storage)
    monkeypatch.setattr("app.routers.reports.get_storage_client", lambda: fake_storage)

    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {_login(client, admin.username)}"}

        # 1. 上传有效 Excel 财务文件并解析
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
        assert upload_resp.status_code == 201
        doc_data = upload_resp.json()["data"]
        doc_id = doc_data["id"]
        assert doc_data["filename"] == "profit_2025_q2.xlsx"
        assert doc_data["status"] in ("pending", "success", "needs_review", "processing")

        # 等待/断言解析任务完成后 financial_reports 表出现对应数据
        doc_resp = client.get(f"/api/v1/documents/{doc_id}", headers=headers)
        assert doc_resp.status_code == 200
        assert doc_resp.json()["data"]["status"] == "success"

        # 断言解析完成后 financial_reports 表出现对应数据
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

        # 2. 低置信度人工复核：上传无数据 Excel
        empty_excel = _make_excel_content([])
        review_resp = client.post(
            "/api/v1/documents/upload",
            files={
                "file": (
                    "empty_2025_q2.xlsx",
                    BytesIO(empty_excel),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            headers=headers,
        )
        assert review_resp.status_code == 201
        review_doc_id = review_resp.json()["data"]["id"]
        review_doc = e2e_db.query(Document).filter(Document.id == review_doc_id).first()
        assert review_doc is not None
        assert review_doc.status == "needs_review"

        # 3. 自然语言查询解析后的数据
        query_resp = client.post(
            "/api/v1/queries/nl2sql",
            headers=headers,
            json={"question": "2025 Q2 营业收入是多少？"},
        )
        assert query_resp.status_code == 200
        query_data = query_resp.json()["data"]
        assert query_data["question"]
        assert "sql" in query_data
        assert any(row.get("revenue") == 10_000_000 for row in query_data["data"])

        # 4. 创建利润表报告并等待生成完成
        create_resp = client.post(
            "/api/v1/reports",
            headers=headers,
            json={
                "title": "2025 Q2 利润表",
                "report_type": "profit",
                "parameters": {"year": 2025, "period": "Q2"},
            },
        )
        assert create_resp.status_code == 201
        report_id = create_resp.json()["data"]["id"]

        get_resp = client.get(f"/api/v1/reports/{report_id}", headers=headers)
        assert get_resp.status_code == 200
        report_data = get_resp.json()["data"]
        assert report_data["status"] in ("reviewing", "success")
        assert report_data["content"]["summary"]

        # 5. 导出报告为 PDF，验证 content_url 与魔数
        pdf_resp = client.post(
            f"/api/v1/reports/{report_id}/export?format=pdf",
            headers=headers,
        )
        assert pdf_resp.status_code == 200
        pdf_data = pdf_resp.json()["data"]
        assert pdf_data["format"] == "pdf"
        assert pdf_data["content_url"].endswith("/report.pdf")
        pdf_uploads = [u for u in fake_storage.uploaded if u["key"].endswith("/report.pdf")]
        assert len(pdf_uploads) == 1
        assert pdf_uploads[0]["data"].startswith(b"%PDF")

        # 6. 导出报告为 Excel，验证 content_url 与魔数
        xlsx_resp = client.post(
            f"/api/v1/reports/{report_id}/export?format=xlsx",
            headers=headers,
        )
        assert xlsx_resp.status_code == 200
        xlsx_data = xlsx_resp.json()["data"]
        assert xlsx_data["format"] == "xlsx"
        assert xlsx_data["content_url"].endswith("/report.xlsx")
        xlsx_uploads = [u for u in fake_storage.uploaded if u["key"].endswith("/report.xlsx")]
        assert len(xlsx_uploads) == 1
        assert xlsx_uploads[0]["data"].startswith(b"PK")

        # 7. 对报告执行 approve
        approve_resp = client.post(
            f"/api/v1/approvals/{report_id}/action",
            headers=headers,
            json={"action": "approve", "comments": "数据准确，同意发布"},
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["data"]["action"] == "approve"

        get_approved_resp = client.get(f"/api/v1/reports/{report_id}", headers=headers)
        assert get_approved_resp.status_code == 200
        assert get_approved_resp.json()["data"]["status"] == "approved"

        # 8. 查询审计日志并断言关键事件
        audit_resp = client.get("/api/v1/audit/logs", headers=headers)
        assert audit_resp.status_code == 200
        logs = audit_resp.json()["data"]["items"]
        actions = {log["action"] for log in logs}
        assert "document.create" in actions
        assert "document.parse.success" in actions or "document.parse.needs_review" in actions
        assert "queries.nl2sql" in actions
        assert "report.create" in actions
        assert "report.generate.success" in actions
        assert "report.export" in actions
        assert "report.approval.approve" in actions


def test_finance_manager_can_upload(
    e2e_db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """finance_manager 可以上传文件."""
    tenant = Tenant(name="FM Tenant", code=f"e2e-fm-{uuid.uuid4().hex[:8]}")
    e2e_db.add(tenant)
    e2e_db.commit()
    e2e_db.refresh(tenant)

    fm = _create_user(e2e_db, tenant, f"fm-{uuid.uuid4().hex[:8]}", role="finance_manager")

    fake_storage = FakeStorageClient()
    monkeypatch.setattr("app.routers.documents.get_storage_client", lambda: fake_storage)
    monkeypatch.setattr("app.tasks.document_tasks.get_storage_client", lambda: fake_storage)

    headers = {"Authorization": f"Bearer {_login(client, fm.username)}"}
    csv_content = b"year,period,revenue\n2025,Q2,10000000\n"
    resp = client.post(
        "/api/v1/documents/upload",
        files={"file": ("profit_2025_q2.csv", BytesIO(csv_content), "text/csv")},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["filename"] == "profit_2025_q2.csv"
    assert len(fake_storage.uploaded) == 1


def test_viewer_cannot_upload(
    client: TestClient,
    viewer_auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """viewer 不能上传文件."""
    monkeypatch.setattr("app.routers.documents.get_storage_client", lambda: FakeStorageClient())

    csv_content = b"year,period,revenue\n2025,Q2,10000000\n"
    resp = client.post(
        "/api/v1/documents/upload",
        files={"file": ("profit_2025_q2.csv", BytesIO(csv_content), "text/csv")},
        headers=viewer_auth_headers,
    )
    assert resp.status_code == 403


def test_viewer_cannot_export_report(
    client: TestClient,
    auth_headers: dict[str, str],
    viewer_auth_headers: dict[str, str],
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """viewer 不能导出报告."""
    fake_storage = FakeStorageClient()
    monkeypatch.setattr("app.routers.reports.get_storage_client", lambda: fake_storage)
    monkeypatch.setattr(generate_report_task, "delay", lambda _report_id: None)

    create_resp = client.post(
        "/api/v1/reports",
        headers=auth_headers,
        json={
            "title": "viewer export test",
            "report_type": "profit",
            "parameters": {"year": 2025, "period": "Q2"},
        },
    )
    assert create_resp.status_code == 201
    report_id = create_resp.json()["data"]["id"]

    report = db_session.query(Report).filter(Report.id == report_id).first()
    assert report is not None
    report.status = "reviewing"
    report.content = {
        "title": "2025年第二季度利润表",
        "summary": "2025年第二季度，公司实现营业收入 10000000.00 元。",
        "sections": [{"name": "营业收入", "metric": "revenue", "value": 10_000_000.0}],
    }
    report.summary = report.content["summary"]
    db_session.commit()

    export_resp = client.post(
        f"/api/v1/reports/{report_id}/export",
        headers=viewer_auth_headers,
    )
    assert export_resp.status_code == 403
