"""Text2SQL 标准问句基准测试.

MVP 阶段定义 10 条常见财务问句，用于验证规则后端的准确率。
后续接入 Vanna 后，可扩展为 LLM 后端的评测集。
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.financial_report import FinancialReport
from app.models.tenant import Tenant

# 10 条标准问句与期望生成的列
STANDARD_QUESTIONS: list[dict[str, str]] = [
    {"question": "2025 年 Q1 营业收入是多少", "expected_column": "revenue"},
    {"question": "2025 年 Q2 净利润是多少", "expected_column": "net_profit"},
    {"question": "2025 年 Q3 营业成本是多少", "expected_column": "operating_cost"},
    {"question": "2025 年 Q1 营业利润是多少", "expected_column": "operating_profit"},
    {"question": "2025 年 Q2 总资产是多少", "expected_column": "total_assets"},
    {"question": "2025 年 Q3 总负债是多少", "expected_column": "total_liabilities"},
    {"question": "2025 年 Q1 所有者权益是多少", "expected_column": "owner_equity"},
    {"question": "2025 年 Q2 经营活动现金流是多少", "expected_column": "cash_flow_operating"},
    {"question": "2025 年 Q3 收入是多少", "expected_column": "revenue"},
    {"question": "2025 年 Q1 利润是多少", "expected_column": "operating_profit"},
]


def _seed_full_data(db_session: Session, tenant: Tenant) -> None:
    """插入完整示例数据."""
    reports = [
        FinancialReport(
            tenant_id=tenant.id,
            year=2025,
            period="Q1",
            revenue=10_000_000.0,
            operating_cost=6_000_000.0,
            operating_profit=2_500_000.0,
            net_profit=2_000_000.0,
            total_assets=50_000_000.0,
            total_liabilities=20_000_000.0,
            owner_equity=30_000_000.0,
            cash_flow_operating=1_500_000.0,
        ),
        FinancialReport(
            tenant_id=tenant.id,
            year=2025,
            period="Q2",
            revenue=12_000_000.0,
            operating_cost=7_000_000.0,
            operating_profit=3_200_000.0,
            net_profit=2_600_000.0,
            total_assets=55_000_000.0,
            total_liabilities=22_000_000.0,
            owner_equity=33_000_000.0,
            cash_flow_operating=2_000_000.0,
        ),
        FinancialReport(
            tenant_id=tenant.id,
            year=2025,
            period="Q3",
            revenue=11_500_000.0,
            operating_cost=6_800_000.0,
            operating_profit=2_900_000.0,
            net_profit=2_300_000.0,
            total_assets=53_000_000.0,
            total_liabilities=21_000_000.0,
            owner_equity=32_000_000.0,
            cash_flow_operating=1_800_000.0,
        ),
    ]
    db_session.add_all(reports)
    db_session.commit()


def test_standard_questions_success_rate(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_tenant: Tenant,
) -> None:
    """10 条标准问句成功率应达到 100%."""
    _seed_full_data(db_session, test_tenant)

    passed = 0
    for item in STANDARD_QUESTIONS:
        response = client.post(
            "/api/v1/queries/nl2sql",
            json={"question": item["question"]},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()["data"]

        if (
            data["sql"] is not None
            and item["expected_column"] in data["sql"]
            and len(data["data"]) == 1
        ):
            passed += 1

    success_rate = passed / len(STANDARD_QUESTIONS)
    assert success_rate >= 1.0, f"标准问句成功率 {success_rate:.0%}，未达标"
