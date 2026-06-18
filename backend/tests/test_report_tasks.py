"""报告生成异步任务测试."""

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.financial_report import FinancialReport
from app.models.report import Report
from app.models.tenant import Tenant
from app.models.user import User
from app.security import get_password_hash
from app.tasks.report_tasks import generate_report_task


def _create_report(db: Session, tenant: Tenant, user: User) -> Report:
    """创建并提交测试报告."""
    report = Report(
        tenant_id=tenant.id,
        created_by=user.id,
        title="测试报告",
        report_type="profit",
        parameters={"year": 2025, "period": "Q2"},
        status="pending",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def _seed_financial(db: Session, tenant: Tenant) -> FinancialReport:
    """创建测试财务数据."""
    financial = FinancialReport(
        tenant_id=tenant.id,
        year=2025,
        period="Q2",
        revenue=1_000_000.0,
        operating_cost=600_000.0,
        operating_profit=300_000.0,
        net_profit=250_000.0,
    )
    db.add(financial)
    db.commit()
    db.refresh(financial)
    return financial


def test_generate_report_task_success() -> None:
    """测试报告生成任务成功."""
    db = SessionLocal()
    try:
        tenant = Tenant(name="Report Task Tenant", code="report-task")
        db.add(tenant)
        db.commit()
        db.refresh(tenant)

        user = User(
            tenant_id=tenant.id,
            username="reporttester",
            email="report@example.com",
            hashed_password=get_password_hash("testpass"),
            role="admin",
            is_active="Y",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        _seed_financial(db, tenant)
        report = _create_report(db, tenant, user)

        result = generate_report_task.delay(report.id).get()

        assert result["status"] == "reviewing"
        assert result["report_id"] == report.id

        db.refresh(report)
        assert report.status == "reviewing"
        assert report.content is not None
        assert report.summary is not None
        assert report.error_message is None
        assert report.content["title"] == "2025年第二季度利润表"
    finally:
        db.close()


def test_generate_report_task_not_found() -> None:
    """测试对不存在的报告执行任务."""
    result = generate_report_task.delay("non-existent-id").get()

    assert result["status"] == "failed"
    assert result["retry"] is False


def test_generate_report_task_missing_data() -> None:
    """测试缺少财务数据时任务失败但不重试."""
    db = SessionLocal()
    try:
        tenant = Tenant(name="Report Missing Tenant", code="report-missing")
        db.add(tenant)
        db.commit()
        db.refresh(tenant)

        user = User(
            tenant_id=tenant.id,
            username="reportmissing",
            email="missing@example.com",
            hashed_password=get_password_hash("testpass"),
            role="admin",
            is_active="Y",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        report = _create_report(db, tenant, user)
        result = generate_report_task.delay(report.id).get()

        assert result["status"] == "failed"
        assert result["retry"] is False
        assert "未找到" in result["error"]

        db.refresh(report)
        assert report.status == "failed"
        assert report.error_message is not None
    finally:
        db.close()
