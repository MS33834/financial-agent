"""报告生成异步任务."""

from typing import Any

from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.report import Report
from app.reporting.generator import ReportGenerationError, ReportGenerator
from app.services.audit_service import log_action


def _get_report(db: Session, report_id: str) -> Report | None:
    """按 ID 获取报告."""
    return db.query(Report).filter(Report.id == report_id).first()


def _update_report_status(
    db: Session,
    report: Report,
    status: str,
    content: dict[str, Any] | None = None,
    summary: str | None = None,
    error_message: str | None = None,
) -> None:
    """更新报告状态与生成结果."""
    report.status = status
    if content is not None:
        report.content = content
    if summary is not None:
        report.summary = summary
    if error_message is not None:
        report.error_message = error_message
    db.commit()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)  # type: ignore[untyped-decorator]
def generate_report_task(self: Any, report_id: str) -> dict[str, Any]:
    """异步生成报告任务.

    Args:
        report_id: 待生成报告的 ID。

    Returns:
        生成结果摘要。
    """
    db = SessionLocal()
    try:
        report = _get_report(db, report_id)
        if report is None:
            return {
                "status": "failed",
                "error": f"Report {report_id} not found",
                "retry": False,
            }

        _update_report_status(db, report, "processing")

        result = ReportGenerator(db).generate(report)

        _update_report_status(
            db,
            report,
            "reviewing",
            content=result["content"],
            summary=result["summary"],
        )

        log_action(
            db=db,
            action="report.generate.success",
            resource=f"report://{report_id}",
        )

        return {
            "report_id": report_id,
            "status": "reviewing",
            "summary": result["summary"],
        }
    except ReportGenerationError as exc:
        report = _get_report(db, report_id)
        if report is not None:
            _update_report_status(
                db,
                report,
                "failed",
                error_message=str(exc),
            )
            log_action(
                db=db,
                action="report.generate.failed",
                resource=f"report://{report_id}",
                result="failed",
                reason=str(exc),
            )
        # 业务错误无需重试
        return {
            "report_id": report_id,
            "status": "failed",
            "error": str(exc),
            "retry": False,
        }
    except Exception as exc:
        report = _get_report(db, report_id)
        if report is not None:
            _update_report_status(
                db,
                report,
                "failed",
                error_message=str(exc),
            )
            log_action(
                db=db,
                action="report.generate.failed",
                resource=f"report://{report_id}",
                result="failed",
                reason=str(exc),
            )
        raise self.retry(exc=exc) from exc
    finally:
        db.close()
