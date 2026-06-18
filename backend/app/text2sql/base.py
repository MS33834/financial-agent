"""Text2SQL 后端抽象接口."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class NL2SQLResult:
    """Text2SQL 生成结果."""

    sql: str | None
    confidence: float
    backend: str
    explanation: str | None = None
    error: str | None = None


class Text2SQLBackend(ABC):
    """自然语言转 SQL 后端基类."""

    name: str = "base"

    @abstractmethod
    def generate_sql(self, question: str) -> NL2SQLResult:
        """根据自然语言问题生成 SQL.

        Args:
            question: 用户自然语言问题

        Returns:
            NL2SQLResult 包含生成的 SQL 与置信度
        """
        raise NotImplementedError
