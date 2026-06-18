"""文档解析器包."""

from app.parser.base import BaseDocumentParser, ParserRegistry
from app.parser.csv_financial_parser import CsvFinancialParser
from app.parser.excel_parser import ExcelParser
from app.parser.pdf_parser import PdfParser
from app.parser.simple_parser import SimpleDocumentParser

__all__ = [
    "BaseDocumentParser",
    "ParserRegistry",
    "CsvFinancialParser",
    "ExcelParser",
    "PdfParser",
    "SimpleDocumentParser",
]
