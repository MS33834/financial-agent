"""审计日志模型."""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDBase


class AuditLog(UUIDBase):
    """关键操作审计日志.

    不可修改、不可删除，保留期 ≥3 年。
    """

    __tablename__ = "audit_logs"

    tenant_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True, comment="租户 ID"
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True, comment="用户 ID"
    )
    action: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="操作类型"
    )
    resource: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="资源标识"
    )
    input_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="输入 SHA256"
    )
    output_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="输出 SHA256"
    )
    model_version: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="模型版本"
    )
    ip: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="IP 地址"
    )
    result: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="结果: success/fail"
    )
    reason: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="失败原因"
    )
