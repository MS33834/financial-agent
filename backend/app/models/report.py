"""报告生成任务模型."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDBase


class Report(UUIDBase):
    """财务报告生成任务."""

    __tablename__ = "reports"

    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    title: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="报告标题"
    )
    report_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="报告类型: profit/balance/cash/custom",
    )
    parameters: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, comment="报告参数"
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="draft",
        comment="状态: draft/pending/reviewing/approved/rejected/published",
    )
    content: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True, comment="报告内容（JSON）"
    )
    content_url: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="导出文件存储地址"
    )
    summary: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="报告摘要"
    )
