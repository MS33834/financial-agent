"""CSV 财务数据解析器."""

import csv
from io import StringIO
from typing import Any

# 单文件最大解析行数，防止恶意大文件耗尽内存
MAX_CSV_ROWS = 100_000


class CsvFinancialParser:
    """解析包含财务指标的 CSV 文件.

    期望 CSV 包含表头，列名支持中英文别名，例如：
    year,period,revenue,operating_cost,net_profit
    2025,Q2,10000000,6000000,2500000
    """

    def __init__(self, content: bytes) -> None:
        """初始化解析器.

        Args:
            content: CSV 文件字节内容。
        """
        self.content = content

    def parse(self) -> list[dict[str, Any]]:
        """解析 CSV 为记录列表.

        Returns:
            每条记录为一个字段字典。

        Raises:
            ValueError: 超过最大行数限制时抛出。
        """
        text = self.content.decode("utf-8-sig")
        reader = csv.DictReader(StringIO(text))
        records: list[dict[str, Any]] = []
        for row in reader:
            records.append(dict(row))
            if len(records) > MAX_CSV_ROWS:
                raise ValueError(
                    f"CSV 行数超过上限 {MAX_CSV_ROWS}，请拆分文件后重试"
                )
        return records

    def confidence(self) -> float:
        """CSV 结构化数据置信度较高."""
        return 0.95
