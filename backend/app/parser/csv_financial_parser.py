"""CSV 财务数据解析器."""

import csv
from io import StringIO
from typing import Any


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
        """
        text = self.content.decode("utf-8-sig")
        reader = csv.DictReader(StringIO(text))
        return [dict(row) for row in reader]

    def confidence(self) -> float:
        """CSV 结构化数据置信度较高."""
        return 0.95
