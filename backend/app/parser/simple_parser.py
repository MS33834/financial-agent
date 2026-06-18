"""简单文档解析器.

MVP 阶段不依赖 OCR / PDF 库，仅根据文件名与扩展名提取基础元数据。
后续可替换为基于 pdfplumber / PyMuPDF / 多模态 LLM 的实现。
"""

from __future__ import annotations

from typing import Any

from app.models.document import Document


class SimpleDocumentParser:
    """基于规则的文件名解析器."""

    def __init__(self, document: Document) -> None:
        """初始化解析器."""
        self.document = document

    def parse(self) -> dict[str, Any]:
        """解析文档并返回结构化结果."""
        filename = self.document.filename
        ext = filename.split(".")[-1].lower() if "." in filename else ""

        return {
            "filename": filename,
            "extension": ext,
            "storage_key": self.document.storage_key,
            "detected_year": self._extract_year(filename),
            "detected_period": self._extract_period(filename),
            "pages": None,
            "tables": [],
        }

    def confidence(self) -> float:
        """返回解析置信度（MVP 固定较低值）."""
        return 0.6

    @staticmethod
    def _extract_year(filename: str) -> int | None:
        """从文件名提取 4 位年份."""
        # 去掉扩展名，再按分隔符拆分
        name = filename.rsplit(".", 1)[0] if "." in filename else filename
        for token in name.replace("_", "-").split("-"):
            if token.isdigit() and len(token) == 4:
                return int(token)
        return None

    @staticmethod
    def _extract_period(filename: str) -> str | None:
        """从文件名提取季度/月份标识."""
        name = filename.rsplit(".", 1)[0] if "." in filename else filename
        lowered = name.lower()
        for marker in ("q1", "q2", "q3", "q4", "h1", "h2"):
            if marker in lowered:
                return marker.upper()
        return None
