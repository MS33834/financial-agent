"""端到端用户旅程测试.

模拟一个典型工作流：
管理员登录 → NL2SQL 查询 → 创建报告 → 审批报告 → 查看审计日志。
同时验证权限边界：viewer 不能审批报告、不能查看审计日志。

注意：异步任务使用独立的 SessionLocal，为避免事务隔离导致任务看不到
未提交数据，本测试使用真实的已提交数据库会话进行准备与断言。
"""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.main import app
from app.models.financial_report import FinancialReport
from app.models.tenant import Tenant
from app.models.user import User
from app.security import get_password_hash


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
            json={"question": "2025年Q2营业收入是多少？"},
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
