"""错误自省日志模型.

记录任务失败、异常分类、根因分析与修复建议，支撑运维排查与 Agent 自我优化。
"""

from __future__ import annotations

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDBase


class ErrorReflection(UUIDBase):
    """错误自省日志.

    由任务失败或异常处理流程自动产生，也可由运维人员补充 resolution。
    """

    __tablename__ = "error_reflections"

    tenant_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True, comment="租户 ID"
    )
    task_name: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True, comment="任务名称"
    )
    task_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True, comment="任务 ID"
    )
    resource_type: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True, comment="资源类型"
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True, comment="资源 ID"
    )
    exception_type: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True, comment="异常类型"
    )
    exception_message: Mapped[str] = mapped_column(
        Text, nullable=False, comment="异常消息"
    )
    stack_trace: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="堆栈信息"
    )
    error_category: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, comment="错误分类"
    )
    root_cause: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="根因分析"
    )
    suggested_fix: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="修复建议"
    )
    retried: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="是否已重试"
    )
    resolved: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="是否已解决"
    )
    resolution: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="解决方案"
    )
