"""MVP Demo 数据初始化脚本.

为指定租户创建 3 个月（Q1/Q2/Q3）示例财务数据，用于 Text2SQL 与报告生成测试。
使用方法:
    cd backend && python scripts/seed_demo_data.py
"""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault("APP_ENV", "development")

from app.database import Base
from app.models.financial_report import FinancialReport
from app.models.tenant import Tenant
from app.models.user import User
from app.security import get_password_hash

DEMO_DATA: list[dict[str, Any]] = [
    {
        "year": 2025,
        "period": "Q1",
        "report_type": "quarterly",
        "revenue": 10_000_000.0,
        "operating_cost": 6_000_000.0,
        "operating_profit": 2_500_000.0,
        "net_profit": 2_000_000.0,
        "total_assets": 50_000_000.0,
        "total_liabilities": 20_000_000.0,
        "owner_equity": 30_000_000.0,
        "cash_flow_operating": 1_500_000.0,
    },
    {
        "year": 2025,
        "period": "Q2",
        "report_type": "quarterly",
        "revenue": 12_000_000.0,
        "operating_cost": 7_000_000.0,
        "operating_profit": 3_200_000.0,
        "net_profit": 2_600_000.0,
        "total_assets": 55_000_000.0,
        "total_liabilities": 22_000_000.0,
        "owner_equity": 33_000_000.0,
        "cash_flow_operating": 2_000_000.0,
    },
    {
        "year": 2025,
        "period": "Q3",
        "report_type": "quarterly",
        "revenue": 11_500_000.0,
        "operating_cost": 6_800_000.0,
        "operating_profit": 2_900_000.0,
        "net_profit": 2_300_000.0,
        "total_assets": 53_000_000.0,
        "total_liabilities": 21_000_000.0,
        "owner_equity": 32_000_000.0,
        "cash_flow_operating": 1_800_000.0,
    },
]


def _get_database_url() -> str:
    """读取数据库连接 URL."""
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is required")
    return url


def _ensure_demo_tenant_and_user(session: Session) -> tuple[Tenant, User]:
    """确保存在默认 demo 租户与管理员用户."""
    tenant = session.query(Tenant).filter(Tenant.code == "demo").first()
    if tenant is None:
        tenant = Tenant(name="Demo Tenant", code="demo", description="MVP 演示租户")
        session.add(tenant)
        session.flush()
        print(f"Created tenant: {tenant.id} ({tenant.name})")

    user = session.query(User).filter(User.username == "demo_admin").first()
    if user is None:
        user = User(
            tenant_id=tenant.id,
            username="demo_admin",
            email="demo@example.com",
            hashed_password=get_password_hash("demo123"),
            role="admin",
            is_active="Y",
        )
        session.add(user)
        session.flush()
        print(f"Created user: {user.id} ({user.username})")

    return tenant, user


def _seed_financial_reports(session: Session, tenant: Tenant) -> None:
    """插入示例财务报表数据."""
    existing = (
        session.query(FinancialReport)
        .filter(FinancialReport.tenant_id == tenant.id, FinancialReport.year == 2025)
        .count()
    )
    if existing >= len(DEMO_DATA):
        print("Demo financial reports already exist, skipping.")
        return

    for item in DEMO_DATA:
        report = FinancialReport(tenant_id=tenant.id, **item)
        session.add(report)

    session.commit()
    print(f"Seeded {len(DEMO_DATA)} financial reports for tenant {tenant.id}")


def main() -> None:
    """脚本入口."""
    database_url = _get_database_url()
    engine = create_engine(database_url)
    Base.metadata.create_all(bind=engine)

    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        tenant, _user = _ensure_demo_tenant_and_user(session)
        _seed_financial_reports(session, tenant)
        session.commit()
        print("Demo data seeded successfully.")
    except Exception as exc:
        session.rollback()
        print(f"Failed to seed demo data: {exc}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
