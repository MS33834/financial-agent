"""仪表盘数据服务测试."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.report import Report
from app.models.tenant import Tenant
from app.models.user import User
from app.services.dashboard_service import (
    _get_approval_trend,
    get_dashboard_summary,
    get_user_greeting,
)


class TestGetDashboardSummary:
    """get_dashboard_summary 测试."""

    def test_empty_tenant_returns_zeros(self, db_session: Session, test_tenant: Tenant) -> None:
        """空租户返回全零汇总."""
        result = get_dashboard_summary(db_session, test_tenant.id)

        assert result["report_count"] == 0
        assert result["pending_approval_count"] == 0
        assert result["document_count"] == 0
        assert result["recent_reports"] == []
        assert result["recent_documents"] == []
        assert result["report_status_distribution"] == {}
        assert result["document_status_distribution"] == {}
        assert result["recent_activities"] == []
        assert len(result["approval_trend"]) == 7

    def test_counts_and_recent_items(
        self, db_session: Session, test_tenant: Tenant, test_user: User
    ) -> None:
        """统计与最近项应正确返回."""
        report = Report(
            tenant_id=test_tenant.id,
            created_by=test_user.id,
            title="Q1 报表",
            status="reviewing",
            report_type="profit",
            parameters={"period": "Q1", "year": 2024},
        )
        document = Document(
            tenant_id=test_tenant.id,
            created_by=test_user.id,
            filename="q1.pdf",
            status="parsed",
            storage_key="q1.pdf",
        )
        audit = AuditLog(
            tenant_id=test_tenant.id,
            user_id=test_user.id,
            action="create_report",
            resource="report",
            result="success",
        )
        db_session.add_all([report, document, audit])
        db_session.commit()

        result = get_dashboard_summary(db_session, test_tenant.id)

        assert result["report_count"] == 1
        assert result["pending_approval_count"] == 1
        assert result["document_count"] == 1
        assert len(result["recent_reports"]) == 1
        assert result["recent_reports"][0]["title"] == "Q1 报表"
        assert len(result["recent_documents"]) == 1
        assert result["recent_documents"][0]["filename"] == "q1.pdf"
        assert result["report_status_distribution"] == {"reviewing": 1}
        assert result["document_status_distribution"] == {"parsed": 1}
        assert len(result["recent_activities"]) == 1
        assert result["recent_activities"][0]["action"] == "create_report"

    def test_status_distribution_grouped(
        self, db_session: Session, test_tenant: Tenant, test_user: User
    ) -> None:
        """状态分布按状态分组统计."""
        reports = [
            Report(
                tenant_id=test_tenant.id,
                created_by=test_user.id,
                title=f"Report {i}",
                status=status,
                report_type="profit",
                parameters={"period": "Q1", "year": 2024},
            )
            for i, status in enumerate(["reviewing", "reviewing", "approved", "rejected"])
        ]
        db_session.add_all(reports)
        db_session.commit()

        result = get_dashboard_summary(db_session, test_tenant.id)
        assert result["report_status_distribution"] == {
            "reviewing": 2,
            "approved": 1,
            "rejected": 1,
        }

    def test_only_current_tenant_data(
        self, db_session: Session, test_tenant: Tenant
    ) -> None:
        """只统计当前租户数据."""
        other = Tenant(name="Other", code="other")
        db_session.add(other)
        db_session.commit()

        user = User(
            tenant_id=other.id,
            username="otheruser",
            email="other@example.com",
            hashed_password="x",
            role="viewer",
            is_active="Y",
        )
        report = Report(
            tenant_id=other.id,
            created_by=user.id,
            title="Other Report",
            status="approved",
            report_type="profit",
            parameters={"period": "Q1", "year": 2024},
        )
        db_session.add_all([user, report])
        db_session.commit()

        result = get_dashboard_summary(db_session, test_tenant.id)
        assert result["report_count"] == 0


class TestGetApprovalTrend:
    """_get_approval_trend 测试."""

    def test_returns_seven_days(self, db_session: Session, test_tenant: Tenant) -> None:
        """返回最近 7 天趋势."""
        trend = _get_approval_trend(db_session, test_tenant.id)
        assert len(trend) == 7
        for item in trend:
            assert "date" in item
            assert "count" in item
            assert item["count"] == 0

    def test_counts_reports_by_day(
        self, db_session: Session, test_tenant: Tenant, test_user: User
    ) -> None:
        """按天统计报告创建数."""
        today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        reports = [
            Report(
                tenant_id=test_tenant.id,
                created_by=test_user.id,
                title="Today Report",
                status="reviewing",
                report_type="profit",
                parameters={"period": "Q1", "year": 2024},
                created_at=today + timedelta(hours=1),
            ),
            Report(
                tenant_id=test_tenant.id,
                created_by=test_user.id,
                title="Today Report 2",
                status="reviewing",
                report_type="profit",
                parameters={"period": "Q1", "year": 2024},
                created_at=today + timedelta(hours=2),
            ),
            Report(
                tenant_id=test_tenant.id,
                created_by=test_user.id,
                title="Yesterday Report",
                status="reviewing",
                report_type="profit",
                parameters={"period": "Q1", "year": 2024},
                created_at=today - timedelta(days=1, hours=-1),
            ),
        ]
        db_session.add_all(reports)
        db_session.commit()

        trend = _get_approval_trend(db_session, test_tenant.id)
        today_label = today.strftime("%m-%d")
        yesterday_label = (today - timedelta(days=1)).strftime("%m-%d")

        today_item = next(item for item in trend if item["date"] == today_label)
        yesterday_item = next(item for item in trend if item["date"] == yesterday_label)
        assert today_item["count"] == 2
        assert yesterday_item["count"] == 1


class TestGetUserGreeting:
    """get_user_greeting 测试."""

    def test_known_roles(self, test_user: User) -> None:
        """已知角色返回对应中文称呼."""
        test_user.role = "admin"
        assert get_user_greeting(test_user) == "管理员，欢迎回来"

        test_user.role = "finance_manager"
        assert get_user_greeting(test_user) == "财务经理，欢迎回来"

        test_user.role = "auditor"
        assert get_user_greeting(test_user) == "审计员，欢迎回来"

        test_user.role = "viewer"
        assert get_user_greeting(test_user) == "查看者，欢迎回来"

    def test_unknown_role_uses_role_name(self, test_user: User) -> None:
        """未知角色直接使用 role 字段."""
        test_user.role = "supervisor"
        assert get_user_greeting(test_user) == "supervisor，欢迎回来"
