"""Excel 财务数据解析器."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from app.parser.base import BaseDocumentParser, ParserRegistry
from app.parser.utils import extract_period, extract_year


@ParserRegistry.register
class ExcelParser(BaseDocumentParser):
    """基于 openpyxl 的 Excel 解析器.

    默认读取第一个工作表，第一行作为表头；
    列名支持中英文别名，由 financial_import_service 统一映射。
    """

    supported_extensions = {"xlsx", "xls"}

    def parse(self, content: bytes, filename: str) -> dict[str, Any]:
        """解析 Excel 内容."""
        try:
            import openpyxl
        except ImportError as exc:
            raise RuntimeError("Excel 解析需要 openpyxl，请安装：pip install openpyxl") from exc

        workbook = openpyxl.load_workbook(filename=BytesIO(content), data_only=True)
        sheet = workbook.active
        if sheet is None:
            return self._empty_result(filename)

        rows = list(sheet.iter_rows(values_only=True))
        if len(rows) < 2:
            return self._empty_result(filename)

        headers = [str(cell).strip() if cell is not None else "" for cell in rows[0]]
        records: list[dict[str, Any]] = []
        for row in rows[1:]:
            record = {header: value for header, value in zip(headers, row, strict=False) if header}
            if any(v is not None and str(v).strip() != "" for v in record.values()):
                records.append(record)

        return {
            "format": "excel",
            "filename": filename,
            "extension": filename.split(".")[-1].lower() if "." in filename else "",
            "sheet_name": sheet.title,
            "detected_year": extract_year(filename),
            "detected_period": extract_period(filename),
            "records": records,
            "tables": [records],
            "row_count": len(records),
            "confidence": 0.95 if records else 0.5,
        }

    def _empty_result(self, filename: str) -> dict[str, Any]:
        return {
            "format": "excel",
            "filename": filename,
            "extension": filename.split(".")[-1].lower() if "." in filename else "",
            "detected_year": extract_year(filename),
            "detected_period": extract_period(filename),
            "records": [],
            "tables": [],
            "row_count": 0,
            "confidence": 0.5,
        }
