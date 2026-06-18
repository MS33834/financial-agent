"""Excel 解析器测试."""

from io import BytesIO
from typing import Any

import pytest

from app.parser.base import ParserRegistry
from app.parser.excel_parser import ExcelParser


def _make_excel_bytes(rows: list[list[Any]]) -> bytes:
    """构造一个简单 xlsx 文件字节流."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    if ws is None:
        raise RuntimeError("No active worksheet")
    for row in rows:
        ws.append(row)

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def test_excel_parser_extracts_records() -> None:
    """Excel 解析器应正确读取表头和记录."""
    content = _make_excel_bytes(
        [
            ["year", "period", "revenue", "net_profit"],
            [2025, "Q2", 1_000_000, 150_000],
        ]
    )
    parser = ExcelParser()

    result = parser.parse(content, "profit_2025_q2.xlsx")

    assert result["format"] == "excel"
    assert result["detected_year"] == 2025
    assert result["detected_period"] == "Q2"
    assert result["row_count"] == 1
    assert result["confidence"] == 0.95
    assert result["records"] == [
        {"year": 2025, "period": "Q2", "revenue": 1_000_000, "net_profit": 150_000},
    ]


def test_excel_parser_registry_match() -> None:
    """ParserRegistry 应优先返回 ExcelParser."""
    parser = ParserRegistry.get_parser("xlsx")
    assert isinstance(parser, ExcelParser)


def test_excel_parser_empty_file() -> None:
    """空 Excel 文件应返回空记录和低置信度."""
    content = _make_excel_bytes([["year", "period"]])
    parser = ExcelParser()

    result = parser.parse(content, "empty.xlsx")

    assert result["records"] == []
    assert result["confidence"] == 0.5


def test_excel_parser_raises_without_openpyxl(monkeypatch: pytest.MonkeyPatch) -> None:
    """未安装 openpyxl 时应抛出清晰错误."""
    monkeypatch.setattr(
        "builtins.__import__",
        lambda name, *args, **kwargs: (
            (_ for _ in ()).throw(ImportError("No module named 'openpyxl'"))
            if name == "openpyxl"
            else __builtins__.__import__(name, *args, **kwargs)
        ),
    )

    parser = ExcelParser()
    with pytest.raises(RuntimeError, match="openpyxl"):
        parser.parse(b"dummy", "file.xlsx")
