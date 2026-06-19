"""API Key 管理与应用测试."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.api_key import ApiKey
from app.models.financial_report import FinancialReport
from app.models.tenant import Tenant
from app.models.user import User
from app.security import create_access_token


def test_create_and_list_api_key(
    client: TestClient, test_user: User
) -> None:
    """测试管理员可创建并列出 API Key."""
    headers = {"Authorization": f"Bearer {create_access_token({'sub': test_user.id})}"}

    response = client.post(
        "/api/v1/api-keys",
        json={"name": "测试 Key", "scopes": ["queries:nl2sql"]},
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == "测试 Key"
    assert data["scopes"] == ["queries:nl2sql"]
    assert data["key"].startswith("fa_")

    list_response = client.get("/api/v1/api-keys", headers=headers)
    assert list_response.status_code == 200
    items = list_response.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["name"] == "测试 Key"


def test_api_key_scope_controls_queries(
    client: TestClient,
    db_session: Session,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """测试 API Key scope 控制查询接口访问."""
    headers = {"Authorization": f"Bearer {create_access_token({'sub': test_user.id})}"}

    # 创建没有 queries:nl2sql scope 的 Key
    resp = client.post(
        "/api/v1/api-keys",
        json={"name": "只读 Key", "scopes": ["reports:read"]},
        headers=headers,
    )
    wrong_key = resp.json()["data"]["key"]

    response = client.post(
        "/api/v1/queries/nl2sql",
        json={"question": "本月收入是多少"},
        headers={"X-API-Key": wrong_key},
    )
    assert response.status_code == 403

    # 创建带正确 scope 的 Key
    resp = client.post(
        "/api/v1/api-keys",
        json={"name": "查询 Key", "scopes": ["queries:nl2sql"]},
        headers=headers,
    )
    right_key = resp.json()["data"]["key"]

    # 写入测试财务数据，确保查询能正常返回
    db_session.add(
        FinancialReport(
            tenant_id=test_tenant.id,
            year=2026,
            period="Q2",
            report_type="profit",
            revenue=100000.0,
        )
    )
    db_session.commit()

    response = client.post(
        "/api/v1/queries/nl2sql",
        json={"question": "2026年Q2营业收入是多少"},
        headers={"X-API-Key": right_key},
    )
    assert response.status_code == 200
    assert response.json()["code"] == 0


def test_api_key_scope_controls_reports(
    client: TestClient,
    test_user: User,
) -> None:
    """测试 API Key scope 控制报告列表访问."""
    headers = {"Authorization": f"Bearer {create_access_token({'sub': test_user.id})}"}

    resp = client.post(
        "/api/v1/api-keys",
        json={"name": "查询 Key", "scopes": ["queries:nl2sql"]},
        headers=headers,
    )
    key = resp.json()["data"]["key"]

    response = client.get("/api/v1/reports", headers={"X-API-Key": key})
    assert response.status_code == 403

    resp = client.post(
        "/api/v1/api-keys",
        json={"name": "报告 Key", "scopes": ["reports:read"]},
        headers=headers,
    )
    key = resp.json()["data"]["key"]

    response = client.get("/api/v1/reports", headers={"X-API-Key": key})
    assert response.status_code == 200
    assert response.json()["code"] == 0


def test_revoke_and_delete_api_key(
    client: TestClient, db_session: Session, test_user: User
) -> None:
    """测试吊销与删除 API Key."""
    headers = {"Authorization": f"Bearer {create_access_token({'sub': test_user.id})}"}

    resp = client.post(
        "/api/v1/api-keys",
        json={"name": "待吊销 Key", "scopes": ["reports:read"]},
        headers=headers,
    )
    key_id = resp.json()["data"]["id"]
    key = resp.json()["data"]["key"]

    # 吊销后查询失败
    revoke_resp = client.post(f"/api/v1/api-keys/{key_id}/revoke", headers=headers)
    assert revoke_resp.status_code == 200

    reports_resp = client.get("/api/v1/reports", headers={"X-API-Key": key})
    assert reports_resp.status_code == 401

    # 删除
    del_resp = client.delete(f"/api/v1/api-keys/{key_id}", headers=headers)
    assert del_resp.status_code == 200
    assert db_session.query(ApiKey).filter(ApiKey.id == key_id).first() is None


def test_viewer_cannot_manage_api_keys(
    client: TestClient, viewer_auth_headers: dict[str, str]
) -> None:
    """测试普通 viewer 无法管理 API Key."""
    response = client.post(
        "/api/v1/api-keys",
        json={"name": "viewer key", "scopes": []},
        headers=viewer_auth_headers,
    )
    assert response.status_code == 403
