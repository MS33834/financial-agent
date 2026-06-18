"""人工审核相关测试."""

from typing import Any, cast

from fastapi.testclient import TestClient


def _create_report(client: TestClient, auth_headers: dict[str, str]) -> str:
    """辅助函数：创建报告并返回 ID."""
    response = client.post(
        "/api/v1/reports",
        json={"title": "审核测试报告", "report_type": "cash"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data: dict[str, Any] = response.json()["data"]
    return cast(str, data["id"])


def test_approve_report(client: TestClient, auth_headers: dict[str, str]) -> None:
    """测试通过审核."""
    report_id = _create_report(client, auth_headers)
    response = client.post(
        f"/api/v1/approvals/{report_id}/action",
        json={"action": "approve", "comments": "同意发布"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["report_id"] == report_id
    assert data["action"] == "approve"

    # 验证报告状态已更新
    report_response = client.get(f"/api/v1/reports/{report_id}", headers=auth_headers)
    assert report_response.json()["data"]["status"] == "approved"


def test_reject_report(client: TestClient, auth_headers: dict[str, str]) -> None:
    """测试驳回审核."""
    report_id = _create_report(client, auth_headers)
    response = client.post(
        f"/api/v1/approvals/{report_id}/action",
        json={"action": "reject", "comments": "数据有误"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["action"] == "reject"


def test_modify_report(client: TestClient, auth_headers: dict[str, str]) -> None:
    """测试退回修改."""
    report_id = _create_report(client, auth_headers)
    response = client.post(
        f"/api/v1/approvals/{report_id}/action",
        json={"action": "modify", "comments": "请修改"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["action"] == "modify"

    report_response = client.get(f"/api/v1/reports/{report_id}", headers=auth_headers)
    assert report_response.json()["data"]["status"] == "draft"


def test_approve_invalid_action(client: TestClient, auth_headers: dict[str, str]) -> None:
    """测试非法审核操作."""
    report_id = _create_report(client, auth_headers)
    response = client.post(
        f"/api/v1/approvals/{report_id}/action",
        json={"action": "freeze"},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_approve_report_not_found(client: TestClient, auth_headers: dict[str, str]) -> None:
    """测试对不存在的报告进行审核."""
    response = client.post(
        "/api/v1/approvals/non-existent-id/action",
        json={"action": "approve"},
        headers=auth_headers,
    )
    assert response.status_code == 404
