"""简单文档解析器.

MVP 阶段作为兜底解析器：当没有安装 pdfplumber/openpyxl/Mineru 时，
仅根据文件名与扩展名提取基础元数据。
"""

from __future__ import annotations

from typing import Any

from app.models.document import Document
from app.parser.base import BaseDocumentParser, ParserRegistry
from app.parser.utils import extract_period, extract_year


@ParserRegistry.register
class SimpleDocumentParser(BaseDocumentParser):
    """基于规则的文件名解析器."""

    supported_extensions = {
        "pdf",
        "doc",
        "docx",
        "xls",
        "xlsx",
        "csv",
        "txt",
        "png",
        "jpg",
        "jpeg",
    }

    def __init__(self, document: Document | None = None) -> None:
        """初始化解析器."""
        self.document = document

    def parse(self, content: bytes, filename: str) -> dict[str, Any]:  # noqa: ARG002
        """解析文档并返回结构化结果."""
        ext = filename.split(".")[-1].lower() if "." in filename else ""

        return {
            "format": ext or "unknown",
            "filename": filename,
            "extension": ext,
            "detected_year": extract_year(filename),
            "detected_period": extract_period(filename),
            "pages": None,
            "tables": [],
            "records": [],
            "text": "",
            "confidence": 0.3,
        }

    def confidence(self) -> float:
        """返回解析置信度（兜底解析器固定较低值）."""
        return 0.3
