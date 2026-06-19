"""PDF 文档解析器.

当前实现：
1. 若配置 Mineru HTTP 服务地址，优先调用外部 Mineru 服务解析；
2. 否则尝试 pdfplumber 提取表格与文本；
3. 预留本地 Mineru / Magic-PDF 接口；
4. 若 pdfplumber 未安装，则降级为 SimpleDocumentParser 兜底。
"""

from __future__ import annotations

from io import BytesIO
from typing import Any

from app.config import get_settings
from app.logger import get_logger
from app.parser.base import BaseDocumentParser, ParserRegistry
from app.parser.mineru_client import MineruClient, MineruError
from app.parser.simple_parser import SimpleDocumentParser
from app.parser.utils import extract_period, extract_year

logger = get_logger(__name__)


@ParserRegistry.register
class PdfParser(BaseDocumentParser):
    """PDF 解析器，支持表格抽取与文本提取."""

    supported_extensions = {"pdf"}

    def parse(self, content: bytes, filename: str) -> dict[str, Any]:
        """解析 PDF 内容."""
        detected_year = extract_year(filename)
        detected_period = extract_period(filename)

        # 优先调用外部 Mineru HTTP 服务
        settings = get_settings()
        if settings.mineru_api_url:
            client = MineruClient(
                api_url=settings.mineru_api_url,
                timeout=settings.mineru_timeout,
            )
            try:
                return client.parse(content, filename)
            except MineruError as exc:
                logger.warning("Mineru 解析失败，降级到 pdfplumber", error=str(exc))

        # 预留：若 Mineru 已安装，可优先使用其高精度解析结果
        if _mineru_available():
            return _parse_with_mineru(content, filename, detected_year, detected_period)

        # 默认使用 pdfplumber 提取表格
        try:
            import pdfplumber
        except ImportError as exc:
            raise RuntimeError("PDF 解析需要 pdfplumber，请安装：pip install pdfplumber") from exc

        tables: list[list[dict[str, Any]]] = []
        all_records: list[dict[str, Any]] = []
        text_parts: list[str] = []
        pages_count = 0

        with pdfplumber.open(BytesIO(content)) as pdf:
            pages_count = len(pdf.pages)
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    text_parts.append(page_text)

                page_tables = page.extract_tables()
                for table in page_tables:
                    if not table or len(table) < 2:
                        continue
                    headers = [str(cell).strip() if cell is not None else "" for cell in table[0]]
                    records: list[dict[str, Any]] = []
                    for row in table[1:]:
                        record = {
                            header: cell
                            for header, cell in zip(headers, row, strict=False)
                            if header
                        }
                        if any(v is not None and str(v).strip() != "" for v in record.values()):
                            records.append(record)
                    if records:
                        tables.append(records)
                        all_records.extend(records)

        confidence = 0.85 if tables else 0.5
        if not all_records:
            # 没有提取到表格时降级为兜底解析器
            fallback = SimpleDocumentParser()
            result = fallback.parse(content, filename)
            result["confidence"] = 0.3
            result["text"] = "\n".join(text_parts)
            return result

        return {
            "format": "pdf",
            "filename": filename,
            "extension": "pdf",
            "detected_year": detected_year,
            "detected_period": detected_period,
            "pages": pages_count,
            "tables": tables,
            "records": all_records,
            "text": "\n".join(text_parts),
            "confidence": confidence,
        }


def _mineru_available() -> bool:
    """检测是否已安装 Mineru / Magic-PDF."""
    import importlib.util

    return importlib.util.find_spec("magic_pdf") is not None


def _parse_with_mineru(
    content: bytes,
    filename: str,
    detected_year: int | None,
    detected_period: str | None,
) -> dict[str, Any]:
    """调用 Mineru 解析 PDF（预留实现）."""
    raise NotImplementedError("Mineru 解析器尚未实现，请先完成 Mineru 服务接入与结果映射。")
