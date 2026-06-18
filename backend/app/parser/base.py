"""文档解析器抽象层.

采用可插拔设计：
- 新增解析器只需继承 BaseDocumentParser 并注册到 ParserRegistry。
- PDF 解析优先尝试 Mineru（若已安装），否则降级到 pdfplumber。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar


class BaseDocumentParser(ABC):
    """文档解析器抽象基类."""

    supported_extensions: ClassVar[set[str]] = set()

    @classmethod
    def supports(cls, ext: str) -> bool:
        """判断该解析器是否支持给定扩展名."""
        return ext.lower().lstrip(".") in cls.supported_extensions

    @abstractmethod
    def parse(self, content: bytes, filename: str) -> dict[str, Any]:
        """解析文档内容.

        Args:
            content: 文件二进制内容。
            filename: 原始文件名，用于从文件名提取 year/period 等元数据。

        Returns:
            解析结果字典，建议包含以下字段：
            - format: 文件格式标识
            - records: 可导入财务数据库的结构化记录列表（可选）
            - tables: 提取的表格列表（可选）
            - pages: 页数（可选）
            - confidence: 置信度 0~1
            - detected_year: 从文件名/内容检测到的年份
            - detected_period: 从文件名/内容检测到的周期
            - text: 全文文本（可选）
        """
        raise NotImplementedError


class ParserRegistry:
    """解析器注册表，按文件扩展名匹配可用解析器."""

    _parsers: list[type[BaseDocumentParser]] = []

    @classmethod
    def register(cls, parser_cls: type[BaseDocumentParser]) -> type[BaseDocumentParser]:
        """注册解析器类（可用作装饰器）."""
        cls._parsers.append(parser_cls)
        return parser_cls

    @classmethod
    def get_parser(cls, ext: str) -> BaseDocumentParser | None:
        """根据扩展名获取第一个匹配的解析器实例."""
        for parser_cls in cls._parsers:
            if parser_cls.supports(ext):
                return parser_cls()
        return None

    @classmethod
    def list_parsers(cls) -> list[type[BaseDocumentParser]]:
        """返回所有已注册解析器类."""
        return list(cls._parsers)
