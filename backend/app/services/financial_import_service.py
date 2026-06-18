"""财务数据导入服务.

将结构化数据（如 CSV 解析结果）写入 financial_reports 表，实现数据闭环。
"""

from typing import Any

from sqlalchemy.orm import Session

from app.models.financial_report import FinancialReport
from app.services.audit_service import log_action

# CSV/JSON 字段到模型字段的映射，支持常见中文/英文列名
FIELD_ALIASES: dict[str, str] = {
    "revenue": "revenue",
    "营业收入": "revenue",
    "销售收入": "revenue",
    "operating_cost": "operating_cost",
    "营业成本": "operating_cost",
    "operating_profit": "operating_profit",
    "营业利润": "operating_profit",
    "net_profit": "net_profit",
    "净利润": "net_profit",
    "total_assets": "total_assets",
    "总资产": "total_assets",
    "total_liabilities": "total_liabilities",
    "总负债": "total_liabilities",
    "owner_equity": "owner_equity",
    "所有者权益": "owner_equity",
    "cash_flow_operating": "cash_flow_operating",
    "经营活动现金流": "cash_flow_operating",
    "经营现金流": "cash_flow_operating",
}


def _normalize_key(key: str) -> str:
    """归一化字段名."""
    return key.strip().lower()


def _to_float(value: Any) -> float | None:
    """将字符串/数字转换为浮点数，失败返回 None."""
    if value is None:
        return None
    if isinstance(value, float | int):
        return float(value)
    cleaned = str(value).replace(",", "").strip()
    if cleaned == "":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def import_financial_record(
    db: Session,
    tenant_id: str,
    year: int,
    period: str,
    data: dict[str, Any],
) -> FinancialReport:
    """导入单条财务记录，存在则更新.

    Args:
        db: 数据库会话。
        tenant_id: 租户 ID。
        year: 年份。
        period: 周期。
        data: 原始字段值字典。

    Returns:
        创建或更新后的 FinancialReport 对象。
    """
    normalized: dict[str, float | None] = {}
    for raw_key, raw_value in data.items():
        model_key = FIELD_ALIASES.get(_normalize_key(raw_key))
        if model_key is not None:
            normalized[model_key] = _to_float(raw_value)

    report = (
        db.query(FinancialReport)
        .filter(
            FinancialReport.tenant_id == tenant_id,
            FinancialReport.year == year,
            FinancialReport.period == period,
        )
        .first()
    )

    if report is None:
        report = FinancialReport(
            tenant_id=tenant_id,
            year=year,
            period=period,
            report_type="summary",
        )
        db.add(report)

    for field in (
        "revenue",
        "operating_cost",
        "operating_profit",
        "net_profit",
        "total_assets",
        "total_liabilities",
        "owner_equity",
        "cash_flow_operating",
    ):
        value = normalized.get(field)
        if value is not None:
            setattr(report, field, value)

    db.commit()
    db.refresh(report)

    log_action(
        db=db,
        action="financial_report.import",
        resource=f"financial_report://{report.id}",
        user=None,
        result="success",
        reason=f"year={year};period={period}",
    )

    return report


def import_financial_records(
    db: Session,
    tenant_id: str,
    records: list[dict[str, Any]],
    default_year: int | None = None,
    default_period: str = "annual",
) -> list[FinancialReport]:
    """批量导入财务记录.

    Args:
        db: 数据库会话。
        tenant_id: 租户 ID。
        records: 记录列表。
        default_year: 记录未指定年份时的默认值。
        default_period: 记录未指定周期时的默认值。

    Returns:
        导入后的 FinancialReport 列表。
    """
    imported: list[FinancialReport] = []
    for record in records:
        year_value = record.get("year") if record.get("year") is not None else default_year
        period_value = record.get("period") if record.get("period") is not None else default_period

        if year_value is None:
            raise ValueError("记录缺少 year 且未提供 default_year")

        year = int(str(year_value))
        period = str(period_value).strip() if period_value else default_period

        imported.append(
            import_financial_record(
                db=db,
                tenant_id=tenant_id,
                year=year,
                period=period,
                data=record,
            )
        )
    return imported
