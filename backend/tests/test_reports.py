"""报告生成任务测试."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.financial_report import FinancialReport
from app.models.tenant import Tenant
from app.tasks.report_tasks import generate_report_task


def _seed_financial(
    db_session: Session,
    tenant_id: str,
    year: int,
    period: str,
) -> FinancialReport:
    """插入测试财务数据."""
    report = FinancialReport(
        tenant_id=tenant_id,
        year=year,
        period=period,
        report_type="summary",
        revenue=10_000_000.0,
        operating_cost=6_000_000.0,
        operating_profit=3_000_000.0,
        net_profit=2_500_000.0,
        total_assets=50_000_000.0,
        total_liabilities=20_000_000.0,
        owner_equity=30_000_000.0,
        cash_flow_operating=4_000_000.0,
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)
    return report


def test_create_report_task(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试创建报告后触发异步生成任务."""
    delayed_ids: list[str] = []

    def fake_delay(report_id: str) -> None:
        delayed_ids.append(report_id)

    monkeypatch.setattr(generate_report_task, "delay", fake_delay)

    payload = {
        "title": "2025 Q2 利润表",
        "report_type": "profit",
        "parameters": {"year": 2025, "period": "Q2", "currency": "CNY"},
    }
    response = client.post("/api/v1/reports", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["title"] == payload["title"]
    assert data["report_type"] == payload["report_type"]
    assert data["status"] == "pending"
    assert data["parameters"] == payload["parameters"]
    assert len(delayed_ids) == 1
    assert data["id"] == delayed_ids[0]


def test_list_reports(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_tenant: Tenant,
) -> None:
    """测试报告列表分页."""
    _seed_financial(db_session, str(test_tenant.id), 2025, "Q1")
    for i in range(2):
        client.post(
            "/api/v1/reports",
            json={
                "title": f"报告 {i}",
                "report_type": "balance",
                "parameters": {"year": 2025, "period": "Q1"},
            },
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
