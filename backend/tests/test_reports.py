"""报告生成任务测试."""

from fastapi.testclient import TestClient


def test_create_report_task(client: TestClient, auth_headers: dict[str, str]) -> None:
    """测试创建报告生成任务."""
    payload = {
        "title": "Q2 利润表",
        "report_type": "profit",
        "parameters": {"period": "2025-Q2", "currency": "CNY"},
    }
    response = client.post("/api/v1/reports", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["title"] == payload["title"]
    assert data["report_type"] == payload["report_type"]
    assert data["status"] == "draft"
    assert data["parameters"] == payload["parameters"]


def test_list_reports(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """测试报告列表分页."""
    for i in range(2):
        client.post(
            "/api/v1/reports",
            json={"title": f"报告 {i}", "report_type": "balance"},
            headers=auth_headers,
        )

    response = client.get("/api/v1/reports?page=1&page_size=10", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_get_report_not_found(client: TestClient, auth_headers: dict[str, str]) -> None:
    """测试获取不存在的报告."""
    response = client.get("/api/v1/reports/non-existent-id", headers=auth_headers)
    assert response.status_code == 404
