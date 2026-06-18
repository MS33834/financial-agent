"""报告模板与渲染工具.

MVP 阶段使用 Python 标准库 string.Template，避免引入额外依赖。
后续可无缝替换为 Jinja2。
"""

from string import Template
from typing import Any

ProfitTemplate = {
    "title": Template("${year}年${period_label}利润表"),
    "summary": Template(
        "${year}年${period_label}，公司实现营业收入 ${revenue:,.2f} 元，"
        "营业成本 ${operating_cost:,.2f} 元，营业利润 ${operating_profit:,.2f} 元，"
        "净利润 ${net_profit:,.2f} 元。"
    ),
    "sections": [
        {"name": "营业收入", "metric": "revenue"},
        {"name": "营业成本", "metric": "operating_cost"},
        {"name": "营业利润", "metric": "operating_profit"},
        {"name": "净利润", "metric": "net_profit"},
    ],
}

BalanceTemplate = {
    "title": Template("${year}年${period_label}资产负债表"),
    "summary": Template(
        "截至 ${year}年${period_label}，公司总资产 ${total_assets:,.2f} 元，"
        "总负债 ${total_liabilities:,.2f} 元，所有者权益 ${owner_equity:,.2f} 元。"
    ),
    "sections": [
        {"name": "总资产", "metric": "total_assets"},
        {"name": "总负债", "metric": "total_liabilities"},
        {"name": "所有者权益", "metric": "owner_equity"},
    ],
}

CashTemplate = {
    "title": Template("${year}年${period_label}现金流量表"),
    "summary": Template(
        "${year}年${period_label}，公司经营活动产生的现金流量净额为 "
        "${cash_flow_operating:,.2f} 元。"
    ),
    "sections": [
        {"name": "经营活动现金流", "metric": "cash_flow_operating"},
    ],
}

TEMPLATE_REGISTRY: dict[str, dict[str, Any]] = {
    "profit": ProfitTemplate,
    "balance": BalanceTemplate,
    "cash": CashTemplate,
}


def _period_label(period: str) -> str:
    """将 period 转换为可读标签."""
    mapping = {
        "Q1": "第一季度",
        "Q2": "第二季度",
        "Q3": "第三季度",
        "Q4": "第四季度",
        "H1": "上半年",
        "H2": "下半年",
        "annual": "全年",
    }
    return mapping.get(period, period)


def _format_value(value: float | None) -> float:
    """None 值格式化为 0.0，便于模板渲染."""
    return 0.0 if value is None else float(value)


def render_report(report_type: str, data: dict[str, Any]) -> dict[str, Any]:
    """根据报告类型和指标数据渲染报告内容.

    Args:
        report_type: 报告类型，如 profit/balance/cash。
        data: 包含 year、period 及各指标数值的字典。

    Returns:
        结构化的报告内容字典。
    """
    template = TEMPLATE_REGISTRY.get(report_type)
    if template is None:
        return {
            "title": f"自定义报告（{report_type}）",
            "period_label": _period_label(data.get("period", "")),
            "sections": [],
            "summary": "暂不支持该报告类型的自动摘要。",
        }

    period_label = _period_label(data.get("period", ""))
    render_data = {
        "year": data.get("year", ""),
        "period_label": period_label,
        "revenue": _format_value(data.get("revenue")),
        "operating_cost": _format_value(data.get("operating_cost")),
        "operating_profit": _format_value(data.get("operating_profit")),
        "net_profit": _format_value(data.get("net_profit")),
        "total_assets": _format_value(data.get("total_assets")),
        "total_liabilities": _format_value(data.get("total_liabilities")),
        "owner_equity": _format_value(data.get("owner_equity")),
        "cash_flow_operating": _format_value(data.get("cash_flow_operating")),
    }

    sections = [
        {
            "name": section["name"],
            "metric": section["metric"],
            "value": render_data[section["metric"]],
        }
        for section in template["sections"]
    ]

    return {
        "title": template["title"].safe_substitute(render_data),
        "period_label": period_label,
        "year": render_data["year"],
        "period": data.get("period", ""),
        "sections": sections,
        "summary": template["summary"].safe_substitute(render_data),
    }
