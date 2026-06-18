"""审计日志相关测试."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.user import User
from app.security import create_access_token, get_password_hash


def test_list_audit_logs(client: TestClient, auth_headers: dict[str, str]) -> None:
    """测试审计日志列表."""
    # 触发一条审计日志
    client.post(
        "/api/v1/reports",
        json={"title": "审计测试报告", "report_type": "custom"},
        headers=auth_headers,
    )

    response = client.get("/api/v1/audit/logs?page=1&page_size=10", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] >= 1
    assert len(data["items"]) >= 1
    assert data["items"][0]["action"] == "report.create"


def test_audit_logs_forbidden_for_non_privileged_user(
    client: TestClient,
    db_session: Session,
    test_tenant: Tenant,
) -> None:
    """测试普通用户无法访问审计日志."""
    normal_user = User(
        tenant_id=test_tenant.id,
        username="normaluser",
        email="normal@example.com",
        hashed_password=get_password_hash("testpass"),
        role="viewer",
        is_active="Y",
    )
    db_session.add(normal_user)
    db_session.commit()
    db_session.refresh(normal_user)

    token = create_access_token({"sub": normal_user.id})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/audit/logs", headers=headers)
    assert response.status_code == 403
