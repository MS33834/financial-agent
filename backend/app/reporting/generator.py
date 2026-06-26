"""报告生成器：从财务数据生成结构化报告."""

from typing import Any

from sqlalchemy.orm import Session

from app.models.financial_report import FinancialReport
from app.models.report import Report
from app.reporting.templates import render_report


class ReportGenerationError(Exception):
    """报告生成异常."""

    pass


class ReportGenerator:
    """基于财务指标生成报告的引擎."""

    def __init__(
        self,
        db: Session,
        custom_templates: dict[str, Any] | None = None,
    ) -> None:
        """初始化生成器.

        Args:
            db: 数据库会话。
            custom_templates: 自定义模板字典，会覆盖默认 TEMPLATE_REGISTRY 中的同名模板。
        """
        self.db = db
        self.custom_templates = custom_templates or {}

    def generate(self, report: Report) -> dict[str, Any]:
        """根据报告参数生成内容.

        Args:
            report: 报告任务 ORM 对象。

        Returns:
            包含 content 与 summary 的字典。

        Raises:
            ReportGenerationError: 未找到对应期间的财务数据或参数无效时抛出。
        """
        parameters = report.parameters or {}
        year = self._parse_year(parameters.get("year"))
        period = self._parse_period(parameters.get("period"))

        financial = self._fetch_financial(report.tenant_id, year, period)
        if financial is None:
            raise ReportGenerationError(f"未找到 {year} 年 {period} 期间的财务数据")

        data = {
            "year": year,
            "period": period,
            "revenue": financial.revenue,
            "operating_cost": financial.operating_cost,
            "operating_profit": financial.operating_profit,
            "net_profit": financial.net_profit,
            "total_assets": financial.total_assets,
            "total_liabilities": financial.total_liabilities,
            "owner_equity": financial.owner_equity,
            "cash_flow_operating": financial.cash_flow_operating,
        }

        content = render_report(
            report.report_type,
            data,
            templates=self.custom_templates,
        )
        return {
            "content": content,
            "summary": content["summary"],
        }

    def _fetch_financial(
        self,
        tenant_id: str,
        year: int,
        period: str,
    ) -> FinancialReport | None:
        """按租户、年份、周期获取财务数据."""
        return (
            self.db.query(FinancialReport)
            .filter(
                FinancialReport.tenant_id == tenant_id,
                FinancialReport.year == year,
                FinancialReport.period == period,
            )
            .first()
        )

    @staticmethod
    def _parse_year(value: Any) -> int:
        """将 year 参数解析为整数."""
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
        raise ReportGenerationError("报告参数缺少有效的 year 字段")

    @staticmethod
    def _parse_period(value: Any) -> str:
        """将 period 参数归一化，空值视为 annual."""
        if not value:
            return "annual"
        return str(value).strip()
