"""报告生成任务服务."""

from typing import Any

from sqlalchemy.orm import Session

from app.models.report import Report
from app.models.user import User
from app.schemas.report import ReportCreate
from app.services.audit_service import log_action
from app.tasks.report_tasks import generate_report_task


def create_report_task(
    db: Session,
    data: ReportCreate,
    user: User,
) -> Report:
    """创建报告生成任务并触发异步生成."""
    report = Report(
        tenant_id=user.tenant_id,
        created_by=user.id,
        title=data.title,
        report_type=data.report_type,
        parameters=data.parameters,
        status="pending",
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    log_action(
        db=db,
        action="report.create",
        resource=f"report://{report.id}",
        user=user,
    )

    generate_report_task.delay(report.id)

    # 异步任务可能已更新数据库，刷新后再返回
    db.refresh(report)
    return report


def get_report(db: Session, report_id: str, tenant_id: str) -> Report | None:
    """按 ID 和租户获取报告."""
    return (
        db.query(Report)
        .filter(Report.id == report_id, Report.tenant_id == tenant_id)
        .first()
    )


def list_reports(
    db: Session,
    tenant_id: str,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Report], int]:
    """分页查询报告列表."""
    query = db.query(Report).filter(Report.tenant_id == tenant_id)
    total = query.count()
    items = (
        query.order_by(Report.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def update_report_status(
    db: Session,
    report: Report,
    status: str,
) -> Report:
    """更新报告状态."""
    report.status = status
    db.commit()
    db.refresh(report)
    return report


def save_report_result(
    db: Session,
    report: Report,
    content: dict[str, Any],
    summary: str,
    status: str = "reviewing",
) -> Report:
    """保存报告生成结果."""
    report.content = content
    report.summary = summary
    report.status = status
    db.commit()
    db.refresh(report)
    return report
