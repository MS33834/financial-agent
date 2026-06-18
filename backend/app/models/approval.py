"""人工审核记录模型."""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDBase


class Approval(UUIDBase):
    """报告人工审核记录."""

    __tablename__ = "approvals"

    report_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    action: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="操作: submit/approve/reject/modify",
    )
    comments: Mapped[str | None] = mapped_column(Text, nullable=True, comment="审核意见")
