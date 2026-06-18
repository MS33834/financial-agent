"""财务报表汇总模型（Text2SQL 示例数据源）."""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDBase


class FinancialReport(UUIDBase):
    """按年份与周期汇总的财务指标."""

    __tablename__ = "financial_reports"

    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    period: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="annual",
        index=True,
        comment="Q1/Q2/Q3/Q4/H1/H2/annual",
    )
    report_type: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="报表类型",
    )

    revenue: Mapped[float | None] = mapped_column(Float, nullable=True)
    operating_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    operating_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_assets: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_liabilities: Mapped[float | None] = mapped_column(Float, nullable=True)
    owner_equity: Mapped[float | None] = mapped_column(Float, nullable=True)
    cash_flow_operating: Mapped[float | None] = mapped_column(Float, nullable=True)
