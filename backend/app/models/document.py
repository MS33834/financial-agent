"""文档（PDF/Excel）解析任务模型."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDBase


class Document(UUIDBase):
    """上传的财务文档及其解析状态."""

    __tablename__ = "documents"

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

    filename: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="原始文件名"
    )
    storage_key: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="对象存储 key"
    )
    file_size: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="文件大小（字节）"
    )
    mime_type: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="文件类型"
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        comment="状态: pending/processing/success/failed",
    )
    confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="解析置信度"
    )
    parse_result: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True, comment="解析结果（结构化数据）"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="错误信息"
    )
