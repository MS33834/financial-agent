"""报告导出服务."""

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.report import Report
from app.models.user import User
from app.services.audit_service import log_action
from app.storage import StorageClient


class ExportFormatError(Exception):
    """不支持的导出格式."""

    pass


def _render_markdown(report: Report) -> bytes:
    """将报告内容渲染为 Markdown 字节."""
    content = report.content or {}
    lines: list[str] = []
    lines.append(f"# {content.get('title', report.title)}")
    lines.append("")
    lines.append(f"- 报告类型：{report.report_type}")
    lines.append(f"- 生成时间：{report.created_at.isoformat() if report.created_at else ''}")
    lines.append(f"- 导出时间：{datetime.now(UTC).isoformat()}")
    lines.append("")

    summary = content.get("summary") or report.summary
    if summary:
        lines.append("## 摘要")
        lines.append(summary)
        lines.append("")

    sections = content.get("sections") or []
    if sections:
        lines.append("## 指标")
        lines.append("")
        lines.append("| 指标 | 数值 |")
        lines.append("|------|------|")
        for section in sections:
            name = section.get("name", "")
            value = section.get("value", "")
            lines.append(f"| {name} | {value} |")
        lines.append("")

    return "\n".join(lines).encode("utf-8")


def _render_json(report: Report) -> bytes:
    """将报告完整内容渲染为 JSON 字节."""
    payload = {
        "id": report.id,
        "title": report.title,
        "report_type": report.report_type,
        "parameters": report.parameters,
        "content": report.content,
        "summary": report.summary,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "exported_at": datetime.now(UTC).isoformat(),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


_RENDERERS: dict[str, Any] = {
    "markdown": _render_markdown,
    "json": _render_json,
}

_CONTENT_TYPES: dict[str, str] = {
    "markdown": "text/markdown; charset=utf-8",
    "json": "application/json; charset=utf-8",
}

_FILE_EXTENSIONS: dict[str, str] = {
    "markdown": "md",
    "json": "json",
}


def export_report(
    db: Session,
    report: Report,
    storage: StorageClient,
    user: User | None,
    fmt: str = "markdown",
) -> str:
    """导出报告到对象存储.

    Args:
        db: 数据库会话。
        report: 已生成的报告。
        storage: 对象存储客户端。
        user: 当前用户，用于审计日志。
        fmt: 导出格式，支持 markdown/json。

    Returns:
        导出的文件访问 URL。

    Raises:
        ExportFormatError: 格式不支持。
        StorageClientError: 上传失败。
    """
    renderer = _RENDERERS.get(fmt)
    if renderer is None:
        raise ExportFormatError(f"不支持的导出格式: {fmt}")

    data = renderer(report)
    ext = _FILE_EXTENSIONS[fmt]
    key = f"reports/{report.tenant_id}/{report.id}/report.{ext}"

    url = storage.upload_bytes(
        key=key,
        data=data,
        content_type=_CONTENT_TYPES[fmt],
        metadata={"report_id": report.id, "report_type": report.report_type},
    )

    report.content_url = url

    log_action(
        db=db,
        action="report.export",
        resource=f"report://{report.id}",
        user=user,
        result="success",
        reason=f"format={fmt};url={url}",
    )

    return url
