"""API Key 模型.

用于向外部系统/第三方客户端开放受控 API 访问。
Key 明文仅创建时返回一次，数据库存储其 SHA-256 哈希。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import UUIDBase

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.user import User


class ApiKey(UUIDBase):
    """租户级 API Key."""

    __tablename__ = "api_keys"

    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属租户",
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="创建人/负责人",
    )
    name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="Key 名称，便于识别用途"
    )
    key_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="API Key 的 SHA-256 哈希"
    )
    scopes: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment="权限范围列表，如 ['queries:nl2sql', 'reports:read']；空表示全部",
    )
    is_active: Mapped[str] = mapped_column(
        String(1), nullable=False, default="Y", comment="是否启用: Y/N"
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True, comment="最后使用时间"
    )
    first_used_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True, comment="首次使用时间"
    )
    usage_count: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=0, comment="累计调用次数"
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True, comment="过期时间"
    )
    rotated_from: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("api_keys.id", ondelete="SET NULL"),
        nullable=True,
        comment="轮换前的旧 Key ID（仅对新 Key 记录）",
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="api_keys")
    user: Mapped["User"] = relationship(back_populates="api_keys")

    __table_args__ = (
        UniqueConstraint("tenant_id", "key_hash", name="uq_tenant_key_hash"),
    )

    def has_scope(self, scope: str) -> bool:
        """检查是否包含指定 scope；空 scope 列表视为拥有全部权限."""
        if not self.scopes:
            return True
        return scope in self.scopes

    def to_dict(self) -> dict[str, Any]:
        """返回可序列化的字段（不含 key_hash 原始值细节）."""
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "name": self.name,
            "scopes": self.scopes or [],
            "is_active": self.is_active,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "first_used_at": self.first_used_at.isoformat() if self.first_used_at else None,
            "usage_count": self.usage_count,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "rotated_from": self.rotated_from,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
