"""Vanna Text2SQL 训练脚本.

用法：
    cd backend && python scripts/train_vanna.py

环境变量：
    DATABASE_URL     数据库连接 URL（必填）
    OLLAMA_MODEL     默认 qwen2.5:7b
    OLLAMA_HOST      默认 http://fa-ollama:11434
"""

from __future__ import annotations

import os
import sys
from typing import Any

from sqlalchemy import create_engine, text

# ------------------------------------------------------------------
# 数据库 DDL 与样例查询
# ------------------------------------------------------------------
FINANCIAL_REPORTS_DDL = """
CREATE TABLE financial_reports (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL,
    year INTEGER NOT NULL,
    period VARCHAR(16) NOT NULL,
    report_type VARCHAR(32),
    revenue FLOAT,
    operating_cost FLOAT,
    operating_profit FLOAT,
    net_profit FLOAT,
    total_assets FLOAT,
    total_liabilities FLOAT,
    owner_equity FLOAT,
    cash_flow_operating FLOAT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
"""

TRAINING_PAIRS: list[dict[str, str]] = [
    {
        "question": "2025 年 Q1 营业收入是多少",
        "sql": "SELECT revenue FROM financial_reports WHERE year = 2025 AND period = 'Q1';",
    },
    {
        "question": "2025 年 Q2 净利润是多少",
        "sql": "SELECT net_profit FROM financial_reports WHERE year = 2025 AND period = 'Q2';",
    },
    {
        "question": "2025 年 Q3 营业成本是多少",
        "sql": "SELECT operating_cost FROM financial_reports WHERE year = 2025 AND period = 'Q3';",
    },
    {
        "question": "2025 年 Q1 营业利润是多少",
        "sql": "SELECT operating_profit FROM financial_reports WHERE year = 2025 AND period = 'Q1';",
    },
    {
        "question": "2025 年 Q2 总资产是多少",
        "sql": "SELECT total_assets FROM financial_reports WHERE year = 2025 AND period = 'Q2';",
    },
    {
        "question": "2025 年 Q3 总负债是多少",
        "sql": "SELECT total_liabilities FROM financial_reports WHERE year = 2025 AND period = 'Q3';",
    },
    {
        "question": "2025 年 Q1 所有者权益是多少",
        "sql": "SELECT owner_equity FROM financial_reports WHERE year = 2025 AND period = 'Q1';",
    },
    {
        "question": "2025 年 Q2 经营活动现金流是多少",
        "sql": "SELECT cash_flow_operating FROM financial_reports WHERE year = 2025 AND period = 'Q2';",
    },
    {
        "question": "2025 年 Q3 收入是多少",
        "sql": "SELECT revenue FROM financial_reports WHERE year = 2025 AND period = 'Q3';",
    },
    {
        "question": "2025 年 Q1 利润是多少",
        "sql": "SELECT operating_profit FROM financial_reports WHERE year = 2025 AND period = 'Q1';",
    },
]


def _require_env(key: str, default: str | None = None) -> str:
    """读取环境变量，缺失时提供默认值或报错."""
    value = os.getenv(key, default)
    if not value:
        print(f"错误：环境变量 {key} 未设置")
        sys.exit(1)
    return value


def _get_sample_data(database_url: str) -> str:
    """读取 financial_reports 表样例数据并格式化为训练文本."""
    engine = create_engine(database_url)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM financial_reports LIMIT 3")
            ).mappings().all()
    except Exception as exc:  # noqa: BLE001
        print(f"警告：无法读取样例数据：{exc!s}")
        return ""

    if not rows:
        return ""

    lines = ["样例数据："]
    for row in rows:
        lines.append(
            f"year={row['year']}, period={row['period']}, "
            f"revenue={row.get('revenue')}, operating_cost={row.get('operating_cost')}, "
            f"operating_profit={row.get('operating_profit')}, net_profit={row.get('net_profit')}, "
            f"total_assets={row.get('total_assets')}, total_liabilities={row.get('total_liabilities')}, "
            f"owner_equity={row.get('owner_equity')}, cash_flow_operating={row.get('cash_flow_operating')}"
        )
    return "\n".join(lines)


def _init_vanna(model: str, host: str) -> Any:
    """初始化 Vanna 客户端（与 app.text2sql.vanna_backend 一致）."""
    try:
        from vanna.chromadb import ChromaDB_VectorStore
        from vanna.ollama import Ollama
    except ImportError:
        print("提示：Vanna 未安装，请运行 pip install -e '.[ai]' 后重试。")
        sys.exit(0)

    class FinancialVanna(ChromaDB_VectorStore, Ollama):  # type: ignore[misc]
        def __init__(self, config: dict[str, Any] | None = None) -> None:
            super().__init__(config=config)

    return FinancialVanna(
        config={
            "model": model,
            "ollama_host": host,
        }
    )


def main() -> None:
    """训练入口."""
    database_url = _require_env("DATABASE_URL")
    ollama_model = _require_env("OLLAMA_MODEL", "qwen2.5:7b")
    ollama_host = _require_env("OLLAMA_HOST", "http://fa-ollama:11434")

    print(f"使用模型: {ollama_model}")
    print(f"Ollama 地址: {ollama_host}")

    vn = _init_vanna(ollama_model, ollama_host)

    print("训练 DDL...")
    vn.train(ddl=FINANCIAL_REPORTS_DDL)

    sample_data = _get_sample_data(database_url)
    if sample_data:
        print("训练样例数据...")
        vn.train(documentation=sample_data)

    print(f"训练 {len(TRAINING_PAIRS)} 条问句-SQL 对...")
    for pair in TRAINING_PAIRS:
        print(f"  - {pair['question']}")
        vn.train(sql=pair["sql"])

    print("Vanna 训练完成。")


if __name__ == "__main__":
    main()
