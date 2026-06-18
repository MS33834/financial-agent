"""ABAC 访问策略模型."""

from typing import Any

from sqlalchemy import JSON, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDBase


class AccessPolicy(UUIDBase):
    """基于属性的访问控制策略."""

    __tablename__ = "access_policies"

    tenant_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
        comment="租户 ID",
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="策略名称")
    resource_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="资源类型，如 report/document/query",
    )
    action: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="操作，如 read/create/update/delete/approve",
    )
    effect: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="allow",
        comment="allow 或 deny",
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,
        comment="优先级，数值越小优先级越高",
    )
    conditions: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="策略条件，如 {'user.department': 'eq:finance'}",
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="策略描述")
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="是否启用",
    )
