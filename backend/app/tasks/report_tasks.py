"""报告生成异步任务."""

from typing import Any

from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.config import get_settings
from app.database import SessionLocal
from app.im import DingTalkBot, FeishuBot, WeComBot
from app.models.im_user_mapping import IMUserMapping
from app.models.report import Report
from app.models.user import User
from app.reporting.generator import ReportGenerationError, ReportGenerator
from app.services.audit_service import log_action

# 平台到机器人类的映射
_PLATFORM_BOTS: dict[str, type[DingTalkBot | FeishuBot | WeComBot]] = {
    "dingtalk": DingTalkBot,
    "feishu": FeishuBot,
    "wecom": WeComBot,
}


def _get_report(db: Session, report_id: str) -> Report | None:
    """按 ID 获取报告."""
    return db.query(Report).filter(Report.id == report_id).first()


def _get_report_creator(db: Session, report: Report) -> User | None:
    """获取报告创建者."""
    if not report.created_by:
        return None
    return db.query(User).filter(User.id == report.created_by).first()


def _notify_approvers(db: Session, report: Report) -> None:
    """报告生成成功后通知具备审批权限的用户.

    根据当前租户内 admin/auditor 用户的 IM 映射以及已配置的 Webhook，
    通过对应平台的机器人主动推送通知。推送失败不影响主流程。
    """
    settings = get_settings()
    configured_platforms = {
        platform
        for platform, webhook in {
            "dingtalk": settings.dingtalk_webhook,
            "feishu": settings.feishu_webhook,
            "wecom": settings.wecom_webhook,
        }.items()
        if webhook
    }
    if not configured_platforms:
        return

    mappings = (
        db.query(IMUserMapping)
        .join(User, IMUserMapping.user_id == User.id)
        .filter(
            IMUserMapping.tenant_id == report.tenant_id,
            User.role.in_(("admin", "auditor")),
            User.is_active == "Y",
            IMUserMapping.platform.in_(configured_platforms),
        )
        .all()
    )
    if not mappings:
        return

    message = (
        f"报告《{report.title}》已生成完毕，当前状态：待审批。\n"
        f"摘要：{report.summary or '无'}"
    )
    sent_platforms: set[str] = set()
    for mapping in mappings:
        if mapping.platform in sent_platforms:
            continue
        bot_cls = _PLATFORM_BOTS.get(mapping.platform)
        if bot_cls is None:
            continue
        try:
            bot_cls().send_message(message)
        except Exception:
            # 通知失败不应阻塞主流程
            continue
        sent_platforms.add(mapping.platform)


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

        creator = _get_report_creator(db, report)
        log_action(
            db=db,
            action="report.generate.success",
            resource=f"report://{report_id}",
            user=creator,
        )

        _notify_approvers(db, report)

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
            creator = _get_report_creator(db, report)
            log_action(
                db=db,
                action="report.generate.failed",
                resource=f"report://{report_id}",
                result="failed",
                reason=str(exc),
                user=creator,
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
            creator = _get_report_creator(db, report)
            log_action(
                db=db,
                action="report.generate.failed",
                resource=f"report://{report_id}",
                result="failed",
                reason=str(exc),
                user=creator,
            )
        raise self.retry(exc=exc) from exc
    finally:
        db.close()
