"""示例财务数据库 schema 与元数据.

MVP 阶段内置一套标准财务表，用于规则后端生成 SQL。
后续可通过 Alembic 迁移或文档解析动态扩展。
"""

from __future__ import annotations

from typing import Any

FINANCIAL_TABLES: dict[str, dict[str, Any]] = {
    "financial_reports": {
        "description": "财务报表汇总表，按年份与季度存储关键指标",
        "columns": {
            "id": "主键",
            "tenant_id": "租户 ID",
            "year": "年份",
            "period": "周期（Q1/Q2/Q3/Q4/H1/H2/annual）",
            "report_type": "报表类型",
            "revenue": "营业收入",
            "operating_cost": "营业成本",
            "operating_profit": "营业利润",
            "net_profit": "净利润",
            "total_assets": "总资产",
            "total_liabilities": "总负债",
            "owner_equity": "所有者权益",
            "cash_flow_operating": "经营活动现金流",
            "created_at": "创建时间",
        },
    },
    "accounts": {
        "description": "会计科目表",
        "columns": {
            "id": "主键",
            "tenant_id": "租户 ID",
            "code": "科目编码",
            "name": "科目名称",
            "category": "类别（asset/liability/equity/revenue/expense）",
            "parent_id": "父科目 ID",
        },
    },
    "vouchers": {
        "description": "记账凭证表",
        "columns": {
            "id": "主键",
            "tenant_id": "租户 ID",
            "voucher_no": "凭证号",
            "date": "凭证日期",
            "description": "摘要",
            "amount": "金额",
            "debit_account_id": "借方科目 ID",
            "credit_account_id": "贷方科目 ID",
        },
    },
}

METRIC_TO_COLUMN: dict[str, str] = {
    "营收": "revenue",
    "收入": "revenue",
    "营业收入": "revenue",
    "营业成本": "operating_cost",
    "成本": "operating_cost",
    "营业利润": "operating_profit",
    "利润": "operating_profit",
    "净利润": "net_profit",
    "净收益": "net_profit",
    "总资产": "total_assets",
    "资产": "total_assets",
    "总负债": "total_liabilities",
    "负债": "total_liabilities",
    "所有者权益": "owner_equity",
    "权益": "owner_equity",
    "现金流": "cash_flow_operating",
    "经营现金流": "cash_flow_operating",
    "经营活动现金流": "cash_flow_operating",
}

PERIOD_MAP: dict[str, str] = {
    "q1": "Q1",
    "一季度": "Q1",
    "第一季度": "Q1",
    "q2": "Q2",
    "二季度": "Q2",
    "第二季度": "Q2",
    "q3": "Q3",
    "三季度": "Q3",
    "第三季度": "Q3",
    "q4": "Q4",
    "四季度": "Q4",
    "第四季度": "Q4",
    "h1": "H1",
    "上半年": "H1",
    "h2": "H2",
    "下半年": "H2",
    "全年": "annual",
    "年度": "annual",
    "年报": "annual",
}
