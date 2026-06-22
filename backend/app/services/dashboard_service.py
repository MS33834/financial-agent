"""仪表盘数据服务."""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.report import Report
from app.models.user import User


def get_dashboard_summary(db: Session, tenant_id: str) -> dict[str, Any]:
    """获取租户仪表盘汇总数据."""
    report_count = (
        db.query(func.count(Report.id)).filter(Report.tenant_id == tenant_id).scalar() or 0
    )
    pending_approval_count = (
        db.query(func.count(Report.id))
        .filter(Report.tenant_id == tenant_id, Report.status == "reviewing")
        .scalar()
        or 0
    )
    document_count = (
        db.query(func.count(Document.id)).filter(Document.tenant_id == tenant_id).scalar() or 0
    )

    recent_reports = (
        db.query(Report)
        .filter(Report.tenant_id == tenant_id)
        .order_by(Report.created_at.desc())
        .limit(5)
        .all()
    )

    recent_documents = (
        db.query(Document)
        .filter(Document.tenant_id == tenant_id)
        .order_by(Document.created_at.desc())
        .limit(5)
        .all()
    )

    report_status_rows = (
        db.query(Report.status, func.count(Report.id))
        .filter(Report.tenant_id == tenant_id)
        .group_by(Report.status)
        .all()
    )

    document_status_rows = (
        db.query(Document.status, func.count(Document.id))
        .filter(Document.tenant_id == tenant_id)
        .group_by(Document.status)
        .all()
    )

    recent_activities = (
        db.query(AuditLog)
        .filter(AuditLog.tenant_id == tenant_id)
        .order_by(AuditLog.created_at.desc())
        .limit(8)
        .all()
    )

    approval_trend = _get_approval_trend(db, tenant_id)

    return {
        "report_count": report_count,
        "pending_approval_count": pending_approval_count,
        "document_count": document_count,
        "recent_reports": [
            {
                "id": r.id,
                "title": r.title,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in recent_reports
        ],
        "recent_documents": [
            {
                "id": d.id,
                "filename": d.filename,
                "status": d.status,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in recent_documents
        ],
        "report_status_distribution": {status: count for status, count in report_status_rows},  # noqa: C416
        "document_status_distribution": {status: count for status, count in document_status_rows},  # noqa: C416
        "recent_activities": [
            {
                "id": a.id,
                "action": a.action,
                "resource": a.resource,
                "result": a.result,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in recent_activities
        ],
        "approval_trend": approval_trend,
    }


def _get_approval_trend(db: Session, tenant_id: str) -> list[dict[str, Any]]:
    """获取最近 7 天报告创建趋势."""
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    trend = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        next_day = day + timedelta(days=1)
        count = (
            db.query(func.count(Report.id))
            .filter(
                Report.tenant_id == tenant_id,
                Report.created_at >= day,
                Report.created_at < next_day,
            )
            .scalar()
            or 0
        )
        trend.append({"date": day.strftime("%m-%d"), "count": count})
    return trend


def get_user_greeting(user: User) -> str:
    """根据用户角色返回问候语."""
    greetings = {
        "admin": "管理员",
        "finance_manager": "财务经理",
        "auditor": "审计员",
        "viewer": "查看者",
    }
    return f"{greetings.get(user.role, user.role)}，欢迎回来"
