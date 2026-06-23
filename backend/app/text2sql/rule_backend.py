"""基于规则的 Text2SQL 后端.

MVP 阶段覆盖常见财务指标查询，不依赖外部 LLM。
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from app.text2sql.base import NL2SQLResult, Text2SQLBackend
from app.text2sql.financial_schema import METRIC_TO_COLUMN, PERIOD_MAP


class RuleBasedText2SQLBackend(Text2SQLBackend):
    """基于关键词与模板的 NL2SQL 后端."""

    name = "rule"

    def generate_sql(self, question: str) -> NL2SQLResult:
        """根据规则生成 SQL."""
        lowered = question.lower().strip()

        # 提取年份
        year = self._extract_year(lowered)
        if year is None:
            year = datetime.now(UTC).year

        # 提取周期
        period = self._extract_period(lowered)

        # 提取指标
        column = self._extract_metric(lowered)
        if column is None:
            return NL2SQLResult(
                sql=None,
                confidence=0.0,
                backend=self.name,
                error="无法识别财务指标或问题类型",
            )

        # 构建 SQL
        conditions = ["tenant_id = :tenant_id"]

        if year is not None:
            conditions.append(f"year = {year}")
        if period is not None:
            conditions.append(f"period = '{period}'")

        sql = f"SELECT {column} FROM financial_reports WHERE {' AND '.join(conditions)}"

        return NL2SQLResult(
            sql=sql,
            confidence=0.7,
            backend=self.name,
            explanation=f"从 financial_reports 查询 {column}，年份 {year}，周期 {period or '未指定'}",
        )

    @staticmethod
    def _extract_year(question: str) -> int | None:
        """提取 4 位年份."""
        match = re.search(r"(?<!\d)(20\d{2})(?!\d)", question)
        return int(match.group(1)) if match else None

    @staticmethod
    def _extract_period(question: str) -> str | None:
        """提取季度/半年/年度标识."""
        for key, value in PERIOD_MAP.items():
            if key in question:
                return value
        return None

    @staticmethod
    def _extract_metric(question: str) -> str | None:
        """提取财务指标对应的列名."""
        # 优先匹配最长、最具体的指标名
        for key in sorted(METRIC_TO_COLUMN, key=len, reverse=True):
            if key in question:
                return METRIC_TO_COLUMN[key]
        return None
