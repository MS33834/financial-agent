"""报告导出服务."""

import json
from datetime import UTC, datetime
from io import BytesIO
from typing import Any

from fpdf import FPDF
from openpyxl import Workbook
from openpyxl.styles import Font
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


def _safe_pdf_text(text: str) -> str:
    """将文本编码为 PDF 核心字体支持的 latin-1 字符集."""
    return text.encode("latin-1", "replace").decode("latin-1")


def _render_pdf(report: Report) -> bytes:
    """将报告内容渲染为 PDF 字节."""
    content = report.content or {}
    title = content.get("title", report.title)
    summary = content.get("summary") or report.summary or ""
    sections = content.get("sections") or []

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, _safe_pdf_text(title), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, f"Report Type: {report.report_type}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(
        0,
        8,
        f"Created At: {report.created_at.isoformat() if report.created_at else ''}",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.cell(0, 8, f"Exported At: {datetime.now(UTC).isoformat()}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    if summary:
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Summary", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 12)
        pdf.multi_cell(0, 8, _safe_pdf_text(summary))
        pdf.ln(5)

    if sections:
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Metrics", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(90, 8, "Metric", border=1)
        pdf.cell(90, 8, "Value", border=1, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 12)
        for section in sections:
            name = section.get("name", "")
            value = section.get("value", "")
            pdf.cell(90, 8, _safe_pdf_text(str(name)), border=1)
            pdf.cell(90, 8, _safe_pdf_text(str(value)), border=1, new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())


def _render_excel(report: Report) -> bytes:
    """将报告内容渲染为 Excel 字节."""
    content = report.content or {}
    title = content.get("title", report.title)
    summary = content.get("summary") or report.summary or ""
    sections = content.get("sections") or []

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Report"

    worksheet["A1"] = title
    worksheet["A1"].font = Font(bold=True, size=16)

    worksheet["A2"] = "Report Type"
    worksheet["B2"] = report.report_type
    worksheet["A3"] = "Created At"
    worksheet["B3"] = report.created_at.isoformat() if report.created_at else ""
    worksheet["A4"] = "Exported At"
    worksheet["B4"] = datetime.now(UTC).isoformat()

    row = 6
    if summary:
        worksheet.cell(row=row, column=1, value="Summary").font = Font(bold=True, size=14)
        row += 1
        worksheet.cell(row=row, column=1, value=summary)
        row += 2

    if sections:
        worksheet.cell(row=row, column=1, value="Metrics").font = Font(bold=True, size=14)
        row += 1
        worksheet.cell(row=row, column=1, value="Metric").font = Font(bold=True)
        worksheet.cell(row=row, column=2, value="Value").font = Font(bold=True)
        row += 1
        for section in sections:
            worksheet.cell(row=row, column=1, value=section.get("name", ""))
            worksheet.cell(row=row, column=2, value=section.get("value", ""))
            row += 1

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


_RENDERERS: dict[str, Any] = {
    "markdown": _render_markdown,
    "json": _render_json,
    "pdf": _render_pdf,
    "xlsx": _render_excel,
}

_CONTENT_TYPES: dict[str, str] = {
    "markdown": "text/markdown; charset=utf-8",
    "json": "application/json; charset=utf-8",
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

_FILE_EXTENSIONS: dict[str, str] = {
    "markdown": "md",
    "json": "json",
    "pdf": "pdf",
    "xlsx": "xlsx",
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
        fmt: 导出格式，支持 markdown/json/pdf/xlsx。

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
